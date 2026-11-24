# Camera

A bay with a camera pod has an Arducam Mega (3 or 5 MP) under its ceiling, looking down on the boards, and
white LEDs beside it that the bay node switches. The node serves the pictures on TCP port 8081, apart from
the bay's page, so that a stream never holds the web server.

:::{status} simulated
Written, simulated, not on hardware: the bay's page against a simulated camera whose frames come from the 3D
viewer, and the node's JPEG cutter on a PC against real JPEGs. No camera has been on a bay node's SPI bus; the
frame rate and the light have not been measured. See [What exists today](../plan/status.md#status-camera).
:::

Needs: a camera pod on the bay and its lead in the node's J6 ([Add a camera](../build/camera.md)). In the
example rack the camera bay is B2, `bay-b2.local`.

## In the browser

```{figure} ../img/web-ui-camera.png
:class: bb-screenshot
:alt: The Camera card of bay B2: a live fisheye view of a GIGA R1 and its display from above, Stop live view and Snapshot, the light set to Auto (on), the camera an Arducam Mega 3MP at 640 × 480, the last frame 78 KB in 40 ms, one stream, a curl command

Simulated node, the frames rendered by the 3D viewer. On the right: the light, the picture settings, the last
frame's size and time, and who is watching.
```

The **Camera** card of `http://bay-b2.local/` has **Live view** and **Snapshot**, the light (**Auto**, **On**,
**Off**), and the picture settings behind the *Picture* line. Under them is the `curl` line for a snapshot,
ready to copy. Watching needs the camera right; changing the settings needs the control right
([Access rules and security](access.md)).

`bayctl` has no camera command: a script uses the two addresses below.

## One frame from a script

```console
$ curl -o b2.jpg 'http://bay-b2.local:8081/snapshot.jpg?light=on'
```

`/snapshot.jpg` answers one JPEG, with its length. The light is switched on for it and the first frame waits
300 ms for the sensor's automatic exposure. A 640 × 480 JPEG is 30 to 60 KB.

On a bay with no camera the port answers `503 Service Unavailable`, `no camera on this bay`, and `present` is
false in `GET /api/camera`; the rest of the node runs as before. Three clients at once, streams and snapshots
together; a fourth gets `503`, `camera busy: too many clients`.

## A live stream

```console
$ ffplay http://bay-b2.local:8081/stream.mjpg
```

`/stream.mjpg` is MJPEG (`multipart/x-mixed-replace`), five frames a second at most. One thread owns the camera
and sends each frame to every client, the page and scripts alike. In the Wi-Fi model of the rack a camera
stream takes about 4 % of the channel's airtime ([Wi-Fi in the rack](wifi.md)).

## The light

The light is lit while frames are taken for a client that wants it, and off when nobody watches. Each client
says what it wants with `?light=on`, `?light=off` or `?light=auto`, on the snapshot or the stream; `auto`, or
no `?light`, is the bay's setting, `on` or `off`. While the bay is reserved, only the reservation holder's wish
switches the light on ([Reserve a bay](reserve-a-bay.md)).

## Picture settings

```{figure} ../img/web-ui-camera-settings.png
:class: bb-screenshot
:width: 440px
:alt: The camera settings of bay B2: resolution, JPEG quality, rotation, the light, white balance cloudy, exposure and gain automatic, brightness +1, contrast 0, saturation -1, sharpness automatic, and a Reset image to auto button

Simulated node; its frames come from the 3D viewer. The upper four settings are the picture's, the rest the
camera's own image processor's.
```

The settings are saved for the bay and reach the camera between two frames: from the card, over HTTP or in
the shell.

| Setting | Values | Notes |
|---|---|---|
| `resolution` | `320x240`, `640x480`, `1280x720`, `1600x1200`, `1920x1080` | 640 × 480 unless set |
| `quality` | `high`, `default`, `low` | JPEG compression |
| `light` | `on`, `off` | what `?light=auto` means; `on` unless set |
| `rotation` | `0`, `90`, `180`, `270` | the page turns the picture; the JPEGs are as taken |
| `exposure` | `auto`, `manual`, or 0 to 30000 (manual) | the sensor's own unit; the manual value is kept in `exposure_value` while automatic |
| `gain` | `auto`, `manual`, or 0 to 1023 (manual) | `gain_value` likewise |
| `white_balance` | `auto`, `sunny`, `office`, `cloudy`, `home` | the camera's presets |
| `brightness` | −4 to 4 | 0 is the camera's default |
| `contrast`, `saturation` | −3 to 3 | |
| `sharpness` | `auto`, 1 to 8 | 3 MP camera only |

Read from [camera.c](../../firmware/bay-node/src/camera.c).

```console
$ curl -s bay-b2.local/api/camera
$ curl -s -X POST bay-b2.local/api/camera -d '{"exposure": 1200, "white_balance": "cloudy", "brightness": -1}'
```

A POST is all or nothing; `"reset": true` puts the image settings back to automatic first. It answers 404 on
a bay with no camera. Colour effects, exposure compensation, mirroring (use `rotation`) and focus are not
offered. The lens is focused once, by hand, when the rack is brought online
([Bring the rack online](../build/bring-the-rack-online.md)). Every field of `/api/camera`:
[Bay node HTTP API](../reference/node-api.md).

## In the node's shell

```console
uart:~$ bay camera
uart:~$ bay camera set white_balance cloudy
uart:~$ bay camera set exposure 1200
uart:~$ bay camera reset
```

`bay camera` prints the model, the clients, the frames and the settings. `bay camera reset` puts the image
settings back to automatic and keeps the resolution, the quality, the light and the rotation.

The camera has no reset pin and its supply no switch, so neither the node nor a command can restart it: a
camera that hangs comes back only with a power cycle of the whole bay. Other symptoms are in
[Troubleshooting](troubleshooting.md).
