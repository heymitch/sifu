Install Sifu locally so I can train my replacement.

---

## Platform

macOS only. Sifu uses CGEventTap and the macOS Accessibility API to observe
input events. It will not run on Linux or Windows.

---

## Steps

### 1 · Clone or update the repository

If `~/sifu` does not exist:

```
git clone https://github.com/heymitch/sifu.git ~/sifu
```

If `~/sifu` already exists:

```
cd ~/sifu && git pull --ff-only
```

### 2 · Install the package

```
pip install -e ~/sifu
```

This installs Sifu in editable mode. The `sifu` command will be available in
the current Python environment.

### 3 · Run bootstrap

```
python3 -c "from sifu.install.bootstrap import run; print(run())"
```

Bootstrap creates the local library directory and prints two keys:

- `library` — the path where Sifu stores workflow data
- `next` — the next command to run

Surface the `next` value to the user verbatim.

### 4 · Grant Accessibility permission

Sifu cannot capture input events without explicit user approval.

Go to: System Settings → Privacy & Security → Accessibility

Add SifuBar to the list and enable the toggle. Sifu will not prompt for this
automatically — it must be granted before capture begins.

### 5 · Report back

Tell the user:

- The `library` path printed by bootstrap
- The `next` step printed by bootstrap
- That Accessibility permission must be granted before starting capture

Do not launch capture automatically. The user decides when Sifu begins
observing. That decision belongs to them.

---

## Notes

- `pip install -e ~/sifu` is idempotent. Safe to re-run.
- Bootstrap is also idempotent. Running it again will not overwrite existing
  library data.
- If `pip` resolves to Python 2, use `pip3` instead.
- The `sifu start` command begins capture. The `sifu context <task>` command
  sets the active task label. Neither runs automatically during install.
