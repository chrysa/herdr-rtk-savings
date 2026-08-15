# Deep-dive — `chrysa/herdr-rtk-savings`

**But (1 phrase).** Plugin Herdr mono-fichier stdlib-Python : un daemon lit en lecture seule la base
d'historique de RTK (Rust Token Killer) et affiche par workspace, dans la sidebar Herdr, une jauge
de taux d'économie de tokens + total économisé (fallback lifetime), sans subprocess `rtk` ni réseau.

## Contexte technique du projet

- **Fichier unique** `monitor.py` (~420 l., stdlib only : `sqlite3`, `fcntl`, `subprocess`, `json`).
- **Manifeste** `herdr-plugin.toml` : actions `start`/`stop`, events `workspace.created`/`pane.created`/`workspace.focused` → `ensure`, pane popup `savings`.
- **Modèle de données consommé** : table `commands(project_path, timestamp, input_tokens, saved_tokens)` de `~/.local/share/rtk/history.db`, ouverte en `mode=ro`. Index `(project_path, timestamp)` exploité par préfixe de sous-arbre + comparaison de chaînes ISO-8601 UTC.
- **Mécanique Herdr** : `herdr workspace report-metadata <ws> --source … --ttl-ms … --token rtk=…` (une variante publiée, les 3 autres `--clear-token`) ; 4 variantes (`rtk`, `rtk_low`, `rtk_hi`, `rtk_sum`) stylées côté config → couleur dynamique malgré l'absence d'ANSI dans les tokens sidebar. `herdr pane list` / `workspace list` en JSON pour mapper cwd→workspace (vote majoritaire).
- **Robustesse** : verrou `flock` sur le pidfile = autorité (pas le pid, recyclable) ; strip du suffixe ` (deleted)` sur `HERDR_BIN_PATH` ; arrêt auto quand le socket Herdr disparaît (3 misses).

**Niche.** L'écosystème Herdr + RTK est très spécifique. Il n'existe pas d'équivalent externe direct
de « jauge d'économie RTK dans la sidebar Herdr ». Les références utiles se réduisent à : (1) la source
de données elle-même (RTK), (2) le pattern « sidebar-token gauge » d'autres plugins Herdr. Les 4 réfs
ci-dessous sont les seules réellement pertinentes ; ne pas forcer un top-10 artificiel.

---

## 1. rtk-ai/rtk — la source de données (SdV du schéma)

- **owner/repo** : `rtk-ai/rtk` (le README chrysa dit « dhamidi/rtk » — dépôt canonique réel = `rtk-ai/rtk`).
- **Stars** : ~76k · **Activité** : active (branche `develop`, ~1 473 commits) · **Langage** : Rust · **Licence** : **Apache-2.0** (permissive, copiable — mais ici on ne copie pas de code, on lit son fichier .db).
- **Fichier/module du pattern** : sous-commande `rtk gain` (dashboard d'économies) ; stockage local `~/.local/share/rtk/`.
- **Mécanisme réel** : RTK intercepte la sortie des commandes shell, la compresse, et enregistre par commande les tokens envoyés/économisés. `rtk gain -p` recalcule le total. `herdr-rtk-savings` **reproduit l'arithmétique de `rtk gain -p`** directement en SQL au lieu de spawner `rtk` — d'où « Numbers match `rtk gain -p` exactly ».
- **Snippet portable (le cœur : requête agrégée par sous-arbre projet)** :

```python
def query_project(conn, root, since):
    sql = ("SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), "
           "COALESCE(SUM(saved_tokens), 0) FROM commands "
           "WHERE (project_path = ? OR substr(project_path, 1, ?) = ?)")
    params = [root, len(root) + 1, root + os.sep]
    if since:                       # timestamps RTK = ISO-8601 UTC → compare string
        sql += " AND timestamp >= ?"
        params.append(since)
    return conn.execute(sql, params).fetchone()
```

- **Étapes d'intégration** : (déjà fait ici) ouvrir `file:{db}?mode=ro` en URI ; NE JAMAIS écrire ; garder le nom de table/colonnes derrière une seule fonction pour absorber une future migration de schéma RTK.
- **Gotchas** : le schéma RTK n'est PAS documenté/garanti stable → la dépendance sur `commands(project_path, input_tokens, saved_tokens, timestamp)` peut casser à une montée de version RTK. Prévoir un `try/except sqlite3.OperationalError` → fallback « pas de données » (déjà partiellement couvert par le `except Exception` du daemon). Vérifier périodiquement `PRAGMA table_info(commands)` contre le README RTK.
- **Flag licence** : Apache-2.0 = permissif. Aucune reprise de code source ; simple lecture de données locales de l'utilisateur → aucun problème de licence.

---

## 2. aorumbayev/herdr-ctx — pattern « report-metadata token » (jumeau le plus proche)

- **owner/repo** : `aorumbayev/herdr-ctx` · **Stars** : ~0 · **Activité** : récente · **Langage** : TypeScript · **Licence** : **MIT** (permissive, copiable).
- **Rôle** : indicateur de fenêtre de contexte Claude par pane, publié comme token `ctx` dans la sidebar Herdr — même primitive Herdr que ce projet, portée *pane* au lieu de *workspace*.
- **Fichier/module** : `src/report.ts`.
- **Mécanisme réel** : hook status-line Claude → lit `context_window.used_percentage` → `herdr pane report-metadata … --token ctx=… --ttl-ms 600000`. Le TTL fait disparaître le token si le producteur meurt — **exactement** la stratégie TTL de `herdr-rtk-savings` (`TTL_MS = POLL_S*20*1000`, `REFRESH_S=600`).
- **Snippet portable (équivalent conceptuel, ligne réelle du projet)** :

```python
args = ["workspace", "report-metadata", workspace_id, "--source", SOURCE,
        "--ttl-ms", str(TTL_MS), "--token", f"{variant}={text}"]
for name in VARIANTS:            # publier une variante, retirer les autres
    if name != variant:
        args += ["--clear-token", name]
```

- **Étapes d'intégration** : rien à porter (déjà appliqué). À retenir pour un futur plugin : (a) choisir la portée `pane` vs `workspace` selon la granularité voulue ; (b) toujours coupler `--ttl-ms` à une boucle de refresh < TTL.
- **Gotchas** : `herdr-ctx` reporte *par message* (piloté par hook), ce projet reporte *par tick* (poll 60 s). Le poll évite un hook RTK/Claude mais introduit jusqu'à 60 s de latence — acceptable ici (« savings barely move minute-to-minute »).
- **Flag licence** : MIT — copiable tel quel si besoin de réutiliser un bout de logique de reporting.

---

## 3. alexarthurs/herdr-sidebar — API socket Herdr & packaging plugin

- **owner/repo** : `alexarthurs/herdr-sidebar` · **Stars** : ~62 · **Activité** : récente (~136 commits) · **Langage** : Rust · **Licence** : **MIT** (permissive).
- **Rôle** : sidebar type VS Code pour Herdr (explorer + git). Référence pour **le dialogue direct avec le socket Herdr** et la structure d'un plugin Herdr « self-contained ».
- **Fichier/module** : crate Rust unique (ratatui/crossterm/serde) parlant à Herdr via son socket API ; `herdr plugin install <owner>/<repo>/plugins/<name>`.
- **Mécanisme réel** : au lieu de spawner le CLI `herdr` par appel (ce que fait `herdr-rtk-savings` via `subprocess.run([HERDR, …])`), il ouvre le socket API directement → moins de latence, pas de dépendance au PATH/`HERDR_BIN_PATH`.
- **Snippet portable (contraste — l'approche CLI actuelle du projet)** :

```python
def herdr_json(*args, key):
    proc = subprocess.run([HERDR, *args], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "herdr call failed")
    return json.loads(proc.stdout)["result"][key]
```

- **Étapes d'intégration (optionnel, si latence/robustesse deviennent un souci)** : remplacer `herdr_cli`/`herdr_json` par une connexion `socket.AF_UNIX` sur `HERDR_SOCKET_PATH` (déjà lu dans le code pour détecter la mort du serveur) et parler le protocole JSON de la socket → supprime toute la gymnastique `herdr_bin()`/` (deleted)`.
- **Gotchas** : passer au socket = coder/maintenir le protocole wire Herdr (non documenté ici) ; la version CLI reste plus simple et suffisante à 1 appel/minute. Ne migrer que si mesure réelle d'un coût.
- **Flag licence** : MIT — le code Rust n'est pas directement portable en Python, mais la *convention d'install* et l'usage socket sont des idées libres à reprendre.

---

## 4. martinstannard/openrtk — RTK côté opencode (validation du choix « lire la donnée RTK »)

- **owner/repo** : `martinstannard/openrtk` · **Stars** : ~179 · **Activité** : récente · **Langage** : TypeScript · **Licence** : **MIT** (permissive).
- **Rôle** : plugin opencode pour RTK — un autre consommateur de RTK, utile comme point de comparaison sur « comment exposer les gains RTK dans un outil ».
- **Mécanisme réel** : enseigne au modèle la méta-commande `rtk gain` (via un `opencode.md`) plutôt que de lire la base — approche « prompt/CLI » vs l'approche « SQL direct read-only » de ce projet. Confirme que lire le .db (comme fait `herdr-rtk-savings`) est le chemin le plus rapide/précis pour un affichage temps réel (pas de dépendance au sous-processus `rtk`).
- **Snippet portable** : n/a (pas de lecture DB ; c'est le contre-exemple qui justifie le design de ce repo). À retenir : si un jour on veut garantir l'égalité stricte avec RTK sans dépendre du schéma, on pourrait au contraire *appeler* `rtk gain -p --json` — mais cela réintroduit un subprocess par workspace, ce que le README rejette explicitement.
- **Étapes d'intégration** : aucune ; sert de repère de conception.
- **Gotchas** : dépendre de `rtk gain` (openrtk) = robuste au schéma mais lent/coûteux ; dépendre du .db (ce projet) = rapide mais fragile au schéma. Trade-off assumé et documenté ici.
- **Flag licence** : MIT — copiable.

---

## Synthèse licences

Toutes les sources sont **permissives** : rtk-ai/rtk = **Apache-2.0**, herdr-ctx / herdr-sidebar / openrtk = **MIT**.
Aucune source copyleft/restrictive (aucun GPL/AGPL/BSL/FSL/Elastic/fair-code). Rien à réimplémenter pour
raison de licence. Le seul risque n'est pas juridique mais technique : le couplage au schéma non-garanti de
la base RTK (`rtk-ai/rtk`).
