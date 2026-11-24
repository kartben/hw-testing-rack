# Camera

A bay with a camera pod has a small camera under its ceiling, looking down on the boards, with white LEDs
beside it. Use it to watch a board's display or LEDs from your desk.

The camera is an Arducam Mega. To fit one, see [Add a camera](../build/camera.md). The examples use bay B2
of the example rack, at `bay-b2.local`.

## In the browser

```{figure} ../img/web-ui-camera.png
:class: bb-screenshot
:alt: The Camera card of bay B2: a live fisheye view of a GIGA R1 and its display from above, Stop live view and Snapshot, the light set to Auto (on), the camera an Arducam Mega 3MP at 640 × 480, the last frame 78 KB in 40 ms, one stream, a curl command

The Camera card of a simulated node, its picture drawn by the 3D viewer.
```

The **Camera** card of `http://bay-b2.local/` has **Live view**, **Snapshot**, the light (**Auto**, **On**,
**Off**) and the picture settings. To watch, you need the camera right. To change the settings, you need the
control right ([Control who can use the rack](access.md)).

## Over HTTP

`bayctl` has no camera command. The node serves the pictures on TCP port 8081:

```console
$ curl -o b2.jpg 'http://bay-b2.local:8081/snapshot.jpg?light=on'
$ ffplay http://bay-b2.local:8081/stream.mjpg
```

`/snapshot.jpg` returns one JPEG, 30 to 60 KB at 640 × 480. `/stream.mjpg` is an MJPEG stream of up to five
frames a second. Up to three clients can watch at once.

The light is on only while someone watches. Add `?light=on`, `?light=off` or `?light=auto` to either
address. `auto` follows the bay's setting. While the bay is reserved, only the person who reserved it can
switch the light on.

## Picture settings

```{figure} ../img/web-ui-camera-settings.png
:class: bb-screenshot
:width: 440px
:alt: The camera settings of bay B2: resolution, JPEG quality, rotation, the light, white balance cloudy, exposure and gain automatic, brightness +1, contrast 0, saturation -1, sharpness automatic, and a Reset image to auto button

The same settings on the bay's page.
```

The node saves the settings for the bay.

| Setting | Values |
|---|---|
| `resolution` | `320x240`, `640x480` (the default), `1280x720`, `1600x1200`, `1920x1080` |
| `quality` | `high`, `default`, `low` |
| `light` | `on` (the default) or `off`: what `?light=auto` does |
| `rotation` | `0`, `90`, `180`, `270`: the page turns the picture, the JPEGs stay as taken |
| `exposure`, `gain` | `auto`, or a number: 0 to 30000 for exposure, 0 to 1023 for gain |
| `white_balance` | `auto`, `sunny`, `office`, `cloudy`, `home` |
| `brightness` | −4 to 4 |
| `contrast`, `saturation` | −3 to 3 |
| `sharpness` | `auto`, 1 to 8 (3 MP camera only) |

Values read from [camera.c](../../firmware/bay-node/src/camera.c).

```console
$ curl -s bay-b2.local/api/camera
$ curl -s -X POST bay-b2.local/api/camera -d '{"exposure": 1200, "white_balance": "cloudy"}'
```

Send `"reset": true` to put the image settings back to automatic. Every field:
[Bay node HTTP API](../reference/node-api.md).

You focus the lens by hand, once: [Focus the camera](../build/bring-the-rack-online.md#focus-the-camera).

## In the node's shell

```console
uart:~$ bay camera
uart:~$ bay camera set white_balance cloudy
uart:~$ bay camera reset
```

`bay camera` prints the camera, its clients and its settings.

## If the camera stops

The node cannot restart the camera. A camera that hangs comes back only when the node itself loses power.
Cycle the bay's row from [the rack's page](rack-page.md#switch-or-cycle-a-row). Every bay of that row restarts.
