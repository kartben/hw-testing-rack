---
myst:
  substitutions:
    workspace: |
      ```console
      $ west init -m REPO_URL --mf firmware/west.yml rack-ws
      $ cd rack-ws
      $ west update
      $ west patch apply
      $ west blobs fetch hal_espressif
      $ west packages pip --install
      ```
    wifi_conf: |
      ```console
      $ cp REPO_DIR/firmware/bay-node/wifi.conf.example REPO_DIR/firmware/bay-node/wifi.conf
      ```
    build_images: |
      ```console
      $ west build --sysbuild -b power_hub/esp32s3/procpu -d build-hub REPO_DIR/firmware/power-hub
      $ west build --sysbuild -b bay_node/esp32s3/procpu -d build-bay REPO_DIR/firmware/bay-node -- -DEXTRA_CONF_FILE=wifi.conf
      ```
    build_option: |
      ```console
      $ west build --sysbuild -b bay_node/esp32s3/procpu -d build-bay REPO_DIR/firmware/bay-node -- -DEXTRA_CONF_FILE=wifi.conf -DCONFIG_BAY_LED_BRIGHTNESS=80
      ```
---

# Build or download the firmware

A rack runs two firmware images, both Zephyr applications for the ESP32-S3 at version 0.5.0:
[firmware/power-hub](../../firmware/power-hub) on the power hub, one per rack, and
[firmware/bay-node](../../firmware/bay-node) on every bay node, the same image whether the bay holds a DATA ×6
or a DATA ×4.  Build them while the PCBs are at the fab: the node's image can then carry your Wi-Fi network,
and both can be signed with your own key.  The images CI builds have neither.

:::{status} bench
Both images build in CI at every push, beside the builds for the stand-in boards.  The node's firmware has run
on native_sim and on bench stand-ins (an M5Stack CoreS3, a XIAO ESP32-S3).  The hub's has served its page from
a XIAO; its bench plan with a real charger has no recorded result.  Neither image has run on a v1.0 PCB:
[What exists today](../plan/status.md#firmware-feature-by-feature).
:::

A DATA ×4's co-processor runs a third image, the logic analyzer.  It is GPL-3.0, not built here and not
shipped with the project: [Logic analyzer](../use/logic-analyzer.md) says where it comes from and how a node
loads it.

## Set up the workspace

The firmware builds in a west workspace of its own, with this repository as the manifest repository.  The
machine needs west and the Zephyr SDK with its `xtensa-espressif_esp32s3_zephyr-elf` toolchain, the one CI
installs ([Zephyr's Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html)
sets both up).

{{ workspace | replace("REPO_URL", repo_url) }}

| Command | What it does |
|---|---|
| `west update` | fetches Zephyr at the commit pinned in [firmware/west.yml](../../firmware/west.yml) (main of 2026-10-16) and the five modules the build needs: `hal_espressif`, `mbedtls`, `tf-psa-crypto`, `mcuboot`, `lvgl` |
| `west patch apply` | applies the eight patch files listed in [zephyr/patches.yml](../../zephyr/patches.yml): changes to USB/IP, the USB host and its hub class, TCP, Wi-Fi and the telnet shell, carried until Zephyr has them.  Not optional: the firmware uses what they add |
| `west blobs fetch hal_espressif` | the Wi-Fi binary blobs |
| `west packages pip --install` | esptool and the other Python packages of the ESP32 build |

Every command below is typed in `rack-ws`.

:::{note}
On Windows keep the workspace and the build directories on a short path (`C:\rack-ws`): `hal_espressif` and
`tf-psa-crypto` have file paths long enough to hit `MAX_PATH`.
:::

## Put your Wi-Fi in the node's image

The rack wants one access point on one fixed channel: choose it first, with the settings of
[Wi-Fi in the rack](../use/wifi.md).  Then copy the example and put the network's name and password in the
copy:

{{ wifi_conf | replace("REPO_DIR", repo_url.split("/")[-1]) }}

```{literalinclude} ../../firmware/bay-node/wifi.conf.example
:language: ini
:caption: firmware/bay-node/wifi.conf.example
```

Built with `-DEXTRA_CONF_FILE=wifi.conf`, the image joins that network at its first boot, beside the networks
stored later with `wifi cred add`.  Every node of the rack takes the same image, and its page and telnet shell
answer with no wire on its UART pads.  `wifi.conf` is git-ignored: the password stays out of the repository,
and goes into every image built with it.

Without `wifi.conf`, each node's network is typed in its shell at
[stage 4 of its checklist](check-the-pcbs/bay-node.md#4-flash-and-ask), on test pads that sit under the node
once it is on its tray.  The hub has no such file: its network is typed on its console USB-C, at
[stage 4 of its own checklist](check-the-pcbs/power-hub.md#4-flash-and-ask).

## Sign with your own key

MCUboot, the bootloader in front of each application, boots only images signed with the key it was built
with.  Without one, the build signs with MCUboot's public test key (`bootloader/mcuboot/root-ec-p256.pem`)
and warns that "any image signed with it boots"; the PCB's page then shows *test key*.  Anyone can then sign
an image the PCB boots (sending it still needs the admin key): fine on a desk and in CI, not for a rack.

Decide before the first flash.  A PCB flashed over USB with MCUboot holds the public half of the key, and from
then on boots only images signed with that key.  Moving from the test key to your own later costs a USB flash
of every PCB, and so does losing the key ([A lost signing key](../use/recover.md#a-lost-signing-key)).

Make the key once, and keep it and a backup outside the repository:

```console
$ python bootloader/mcuboot/scripts/imgtool.py keygen -t ecdsa-p256 -k ~/keys/rack-signing.pem
$ export HWTR_SIGNING_KEY=$HOME/keys/rack-signing.pem
```

`HWTR_SIGNING_KEY` is an absolute path, read by both builds.  A build line can take the path instead, after
`--`: `-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"/path/to/key.pem\"`.  After changing it, build pristine: add `-p`
to the build lines below.

## Build the two images

{{ build_images | replace("REPO_DIR", repo_url.split("/")[-1]) }}

Leave `-- -DEXTRA_CONF_FILE=wifi.conf` out for a node image without a network.

`--sysbuild` builds MCUboot in front of the application and signs the application for it.  Without it the
build is the application alone: a PCB flashed that way takes no update over the network until it is flashed
again over USB with MCUboot.

Each build leaves two files.  The node's:

- `build-bay/mcuboot/zephyr/zephyr.bin` is MCUboot;
- `build-bay/bay-node/zephyr/zephyr.signed.bin` is the signed application: what `west flash` writes after
  MCUboot, and the file an [update over the network](../use/update-firmware.md) sends.

The hub's are at the same places under `build-hub`, with `power-hub` for `bay-node`.  The build writes an
image id into the signed file, `power-hub/power_hub` or `bay-node/bay_node`: a node refuses the hub's image,
and the hub a node's.

[Flash the hub and the nodes](flash.md) writes them at [stage 4 of the checklists](check-the-pcbs/index.md).
The same two applications also build for the bench stand-ins and for the tests on native_sim:
[Work on the firmware](../engineering/work-on-the-firmware.md).

## Options a builder may change

The defaults suit a rack.  To change one, add the option at the end of a build line, after `--`:

{{ build_option | replace("REPO_DIR", repo_url.split("/")[-1]) }}

`CONFIG_BAY_` options go on the node's build line, `CONFIG_HUB_` options on the hub's, `CONFIG_HWTR_` options
on either.

`CONFIG_BAY_PORTS_ON_AT_BOOT`, default `y`
: Every port of the DATA board comes on at boot, one after the other.  With `n` the ports stay off until
  switched on.

`CONFIG_BAY_DATA_POWER_AT_BOOT`, default `y`
: The DATA lead is powered at boot, once its checks pass.  With `n` it stays off until `bay power on`.

`CONFIG_BAY_PORTS_LIMIT_MW`, default 25000
: What a bay may draw on its DATA lead when no hub grants it a share: a bay outside a rack.

`CONFIG_BAY_LED_BRIGHTNESS`, default 40
: The bay LED's brightness, 1 to 255.

`CONFIG_BAY_CAMERA_FPS`, default 5
: The cap on the camera's stream, 1 to 30 frames a second.

`CONFIG_HWTR_NET_TX_POWER_DBM`, default 11
: Wi-Fi transmit power, 2 to 20 dBm.  `radio <dBm>` changes it on a running node or hub and saves it.

`CONFIG_HUB_BUDGET_MARGIN_PCT`, default 10
: The share of the charger's contract kept free below the rows' budget.  `hub budget margin` changes it on a
  running hub.

`CONFIG_HUB_ROW_CYCLE_MS`, default 2000
: How long a row stays off when it is power-cycled.

`CONFIG_HUB_EPR_ALLOWED`, off by default
: Leave it off.  It unlocks a 28 V contract, and the DATA ×4's L2 inductor withstands 30 V
  ([the power design document](../power.md)).

Every option has the reason for its default in its help text:
[firmware/bay-node/Kconfig](../../firmware/bay-node/Kconfig),
[firmware/power-hub/Kconfig](../../firmware/power-hub/Kconfig),
[firmware/common/Kconfig](../../firmware/common/Kconfig).  What a node and a hub store while they run (a name,
the networks, the access key) is not a build option:
[What a node and a hub remember](../use/recover.md#what-a-node-and-a-hub-remember-and-how-to-wipe-it).

## The images CI builds, and what you give up

The *Firmware* workflow ([.github/workflows/firmware.yml](../../.github/workflows/firmware.yml)) builds both
images at every push and keeps them as artefacts of the run, `firmware-power_hub-test-key` and
`firmware-bay_node-test-key`, each with MCUboot's `zephyr.bin` and the application's `zephyr.signed.bin`.
They are downloaded from a run's page under
{{ '[the repository\'s Actions]({}/actions/workflows/firmware.yml)'.format(repo_url) }}.

| With CI's images | What it costs |
|---|---|
| A GitHub login | the artefacts are served to signed-in users only, and the site publishes no firmware image |
| They expire | GitHub removes a run's artefacts after its retention time: take them from a recent run and keep the files |
| MCUboot's public test key | the artefact's name says it.  Anyone can sign an image these PCBs boot, and moving to your own key later is a USB flash of every PCB |
| No network in the node's image | each node's Wi-Fi is typed in its shell at [stage 4 of its checklist](check-the-pcbs/bay-node.md#4-flash-and-ask).  Miss that moment and [the tray comes out again](index.md#wifi): the pads are under the node |
| No build directory | `west flash` reads one.  Without it the two files go on with esptool, at the addresses of [What west flash writes](flash.md#what-west-flash-writes); nobody has done that with these artefacts |

A command on this page that does not work as written:
[report it](../reference/known-limitations.md#report-a-finding).
