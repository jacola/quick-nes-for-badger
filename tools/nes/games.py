"""Supported user-supplied cartridges. No ROM data is distributed."""
GAMES = {
    "zelda": {
        "title":"Zelda", "label":"Zelda", "prefix":"",
        "filename":"game.nes", "size":131088, "mapper":1, "magic":"ZELDAST1",
        "sha256":"89232edf4f9b52e3cb872094bc78973de080befca2ddea893b6e936066514d4e",
        "description":"Play the original Legend of Zelda with manual checkpoints on the Universe 2026 badge.",
    },
    "mario": {
        "title":"Super Mario Bros.", "label":"Mario", "prefix":"mario_",
        "filename":"Super Mario Bros. (World).nes", "size":40976, "mapper":0, "magic":"MARIOST1",
        "sha256":"0b3d9e1f01ed1668205bab34d6c82b0e281456e137352e4f36a9b2cfa3b66dea",
        "description":"Play the original Super Mario Bros. with manual checkpoints on the Universe 2026 badge.",
        "nes2_header":"4e45531a020101080000000002000001",
    },
    "contra": {
        "title":"Contra", "label":"Contra", "prefix":"contra_",
        "filename":"Contra (USA).nes", "size":131088, "mapper":2, "magic":"CONTRAST",
        "sha256":"26541a5550ee22deeb3d5484e4a96130219b58cff74d068fb1eb6567fa5e5519",
        "description":"Play the original Contra with manual checkpoints on the Universe 2026 badge.",
    },
    "mario3": {
        "title":"Super Mario Bros. 3", "label":"Mario 3", "prefix":"mario3_",
        "filename":"Super Mario Bros. 3 (USA) (Rev 1).nes", "size":393232, "mapper":4, "magic":"SMB3ST01",
        "sha256":"4377a7f5e6eb50bdd2ac6f249bf1a7085500aca8eb41f38545c3a2731c51a579",
        "description":"Play the original Super Mario Bros. 3 with manual checkpoints on the Universe 2026 badge.",
    },
    "megaman2": {
        "title":"Mega Man 2", "label":"Mega Man 2", "prefix":"megaman2_",
        "filename":"Mega Man 2 (USA).nes", "size":262160, "mapper":1, "magic":"MM2STATE",
        "sha256":"49136b412ff61beac6e40d0bbcd8691a39a50cd2744fdcdde3401eed53d71edf",
        "description":"Play the original Mega Man 2 with manual checkpoints on the Universe 2026 badge.",
    },
    "finalfantasy": {
        "title":"Final Fantasy (USA)", "label":"Final Fantasy USA", "prefix":"finalfantasy_",
        "filename":"Final Fantasy (USA).nes", "size":262160, "mapper":1, "magic":"FF1STATE",
        "sha256":"d360beeee19a69d1c92d02292167c57f2d3ca8405b79101fc8c2f39dea549667",
        "description":"Play the original Final Fantasy with manual checkpoints on the Universe 2026 badge.",
    },
    "finalfantasyjp": {
        "title":"Final Fantasy (Japan Rev B)", "label":"Final Fantasy JP", "prefix":"finalfantasyjp_",
        "filename":"Final Fantasy (Japan) (Rev B).nes", "size":262160, "mapper":1, "magic":"FFJPST01",
        "sha256":"d0b0ff41a6b8afb9567c665056d4674ccb9fdd0025a5d3d1c517caa810ff9455",
        "description":"Play the original Japanese Final Fantasy Rev B with manual checkpoints on the Universe 2026 badge.",
    },
    "tetris": {
        "title":"Tetris (Tengen)", "label":"Tetris", "prefix":"tetris_",
        "filename":"Tetris (USA) (Tengen) (Unl).nes", "size":49168, "mapper":3, "magic":"TETRIST1",
        "sha256":"93be1e87830a17024e89fde85d4adb28dd6976a01a825bd713b40f505401560b",
        "description":"Play the original Tengen Tetris with manual checkpoints on the Universe 2026 badge.",
    },
}
