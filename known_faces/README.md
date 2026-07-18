# Face database

Enrolled face photos are **not** committed to this repository — they are biometric
data of real people and stay on the kiosk device only.

To populate this folder, create one sub-folder per group and drop in photos:

```
known_faces/
└── Students/
    ├── Priya Sharma.jpg          # flat file: person's name = filename
    └── Arjun Mehta/              # or a folder per person
        ├── Arjun Mehta.jpg
        └── Arjun Mehta.txt       # optional details for the greeting screen
```

Only groups listed in `ENABLED_GROUPS` in `config.py` are loaded. Press `R` on
the kiosk (or restart it) after adding photos. People enrolled at the kiosk
(`E` key) are saved into the group set by `ENROLL_GROUP`.
