# Auto Join

A TavernLauncher addon that joins a server as soon as the launcher opens. Put a flag in Steam's
Launch Options and Steam's Play button takes you straight into the server, with no launcher window
in the way.

## Install

1. Copy the `autojoin` folder into the `addons` folder next to `TavernLauncher - Client.exe`.
2. Open TavernLauncher, click **🧩 Addons**, tick **Auto Join**, click **Save**, then restart the launcher.
3. Join your server once the normal way, so your username and game path are saved.

## Flags

| Flag | What it does |
| --- | --- |
| `--join-last` | Joins the server selected in the launcher (the last one you picked or joined). |
| `--join host:port` | Joins that server. The port is optional and defaults to 1757. |
| `--hide` | Keeps the launcher window hidden while it joins. Use it with `--join` or `--join-last`. |

## Steam setup

Open **🌍 Community Servers**, select a server, and click **Steam Launch Options**. It shows the
launch options for that server and where your launcher is, each with a Copy button.

**If A Township Tale is in your Steam library:** right-click A Township Tale, open Properties, and
paste this into Launch Options (use your real launcher path):

```
"C:\path\to\TavernLauncher - Client.exe" --join-last --hide %command%
```

Steam's Play button now starts the launcher in the background, and the launcher joins the server.

**If it isn't, or you want one entry per server:** in Steam, click Games, then Add a Non-Steam
Game to My Library, and pick `TavernLauncher - Client.exe`. Right-click the new entry, open
Properties, rename it if you like, and paste this into Launch Options:

```
--join myserver.com:1757 --hide
```

Add it again for each server you want its own entry. Turn on "Include in VR Library" to start it
from the SteamVR dashboard.

## How --hide behaves

- The launcher window stays hidden and the game starts on its own.
- The window shows up only when something needs you: an error, a password or whitelist prompt, a
  launcher update, or a game that hasn't started after 20 seconds.
- When the game closes, the hidden launcher closes too, so Steam stops showing you as playing.
- Leave out `--hide` to keep the launcher window open, like a normal launch.

## Good to know

- If you accept a launcher update, that one launch opens normally without joining.
- If the launcher opens but doesn't join, check its log for a line starting with `Auto Join:`.
