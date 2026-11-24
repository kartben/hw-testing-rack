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

A rack runs two Zephyr images: [firmware/power-hub](../../firmware/power-hub) on the power hub and
[firmware/bay-node](../../firmware/bay-node) on every bay node. Build them yourself while the PCBs are on their
way. Your own images can carry your Wi-Fi network, and you sign them with your own key. The images from CI
have no network and use a public test key.

The co-processor of a DATA ×4 runs a third image, the logic analyzer. You build it separately:
[Load the analyzer image](../use/logic-analyzer.md#load-the-analyzer-image-once) gives the steps.

## Set up the workspace

You need west and the Zephyr SDK with its `xtensa-espressif_esp32s3_zephyr-elf` toolchain.
[Zephyr's Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html)
installs both. Then make a workspace with this repository as its manifest:

{{ workspace | replace("REPO_URL", repo_url) }}

Do not skip `west patch apply`. It applies the patches to Zephyr that the firmware needs
([zephyr/patches.yml](../../zephyr/patches.yml)). Run every command on this page from `rack-ws`.

:::{note}
On Windows, keep the workspace on a short path such as `C:\rack-ws`. Some files of `hal_espressif` and
`tf-psa-crypto` have paths long enough to hit `MAX_PATH`.
:::

## Put your Wi-Fi in the node's image

The rack needs one access point on one fixed channel. Choose it first:
[Wi-Fi for the rack](../use/wifi.md). Then copy the example file and put your network's name and password in
the copy:

{{ wifi_conf | replace("REPO_DIR", repo_url.split("/")[-1]) }}

```{literalinclude} ../../firmware/bay-node/wifi.conf.example
:language: ini
:caption: firmware/bay-node/wifi.conf.example
```

A node built with `-DEXTRA_CONF_FILE=wifi.conf` joins that network at its first boot. Every node takes the
same image. Git ignores `wifi.conf`, so the password stays out of the repository. Every image you build with
it contains the password, so keep those images to yourself.

Without `wifi.conf`, you type each node's network on its UART pads during
[its checklist](check-the-pcbs/bay-node.md), [before it goes on its tray](index.md#wifi). The hub has no such
file: you type its network on its console USB-C during [its own checklist](check-the-pcbs/power-hub.md).

## Sign with your own key

MCUboot, the bootloader, boots only images signed with the key it was built with. If you give no key, the
build uses MCUboot's public test key. It warns you, and the PCB's web page shows *test key*. Anyone can then
sign an image that your PCBs will boot. That is acceptable for one bay on your desk. For a rack, make your
own key.

Do it before the first flash. To change the key later, or to replace a lost one, you must flash every PCB over
USB again ([A lost signing key](../use/recover.md#a-lost-signing-key)).

Make the key once. Keep it, and a backup, outside the repository:

```console
$ python bootloader/mcuboot/scripts/imgtool.py keygen -t ecdsa-p256 -k ~/keys/rack-signing.pem
$ export HWTR_SIGNING_KEY=$HOME/keys/rack-signing.pem
```

Both builds read the key's path from `HWTR_SIGNING_KEY`. The path must be absolute. You can also give it on
the build line, after `--`: `-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"/path/to/key.pem\"`. After you change the
key, add `-p` to the build lines for a pristine build.

## Build the two images

{{ build_images | replace("REPO_DIR", repo_url.split("/")[-1]) }}

For a node image without a network, leave out `-- -DEXTRA_CONF_FILE=wifi.conf`.

Keep `--sysbuild`. It builds MCUboot and signs the application for it. A PCB flashed without MCUboot cannot
take an [update over the network](../use/update-firmware.md) until you flash it again over USB.

Each build leaves two files. For the node:

| File | What it is |
|---|---|
| `build-bay/mcuboot/zephyr/zephyr.bin` | MCUboot |
| `build-bay/bay-node/zephyr/zephyr.signed.bin` | the signed application, the file a network update sends |

The hub's two files are in the same places under `build-hub`, with `power-hub` in place of `bay-node`. Each
image carries its own name, so a node refuses the hub's image and the hub refuses a node's.

You flash the images in the Flash and check step of the hub's and the node's checklists:
[Flash the hub and the nodes](flash.md).

## Options you can change

The defaults suit a rack. To change one, add it at the end of the build line, after `--`:

{{ build_option | replace("REPO_DIR", repo_url.split("/")[-1]) }}

`CONFIG_BAY_` options go on the node's line, `CONFIG_HUB_` options on the hub's, `CONFIG_HWTR_` options on
either.

`CONFIG_BAY_PORTS_ON_AT_BOOT`, default `y`
: Every port of the DATA board comes on at boot. With `n` they stay off until you switch them on.

`CONFIG_BAY_DATA_POWER_AT_BOOT`, default `y`
: The DATA lead is powered at boot, once its checks pass. With `n` it waits for `bay power on`.

`CONFIG_BAY_PORTS_LIMIT_MW`, default 25000
: The power a bay may draw on its DATA lead when no hub grants it a share, as on a desk.

`CONFIG_BAY_LED_BRIGHTNESS`, default 40
: The bay LED's brightness, 1 to 255.

`CONFIG_BAY_CAMERA_FPS`, default 5
: The camera's frame rate cap, 1 to 30.

`CONFIG_HWTR_NET_TX_POWER_DBM`, default 11
: Wi-Fi transmit power, 2 to 20 dBm. `radio <dBm>` changes it on a running PCB.

`CONFIG_HUB_BUDGET_MARGIN_PCT`, default 10
: The share of the charger's power that the hub keeps in reserve, in per cent. `hub budget margin` changes it
  on a running hub.

`CONFIG_HUB_ROW_CYCLE_MS`, default 2000
: How long a row stays off when you power-cycle it.

Each option's help text explains its default:
[firmware/bay-node/Kconfig](../../firmware/bay-node/Kconfig),
[firmware/power-hub/Kconfig](../../firmware/power-hub/Kconfig),
[firmware/common/Kconfig](../../firmware/common/Kconfig).

## Download the images from CI

CI builds both images at every push. Download the artefacts `firmware-power_hub-test-key` and
`firmware-bay_node-test-key` from a run of the *Firmware* workflow, under
{{ '[the repository\'s Actions]({}/actions/workflows/firmware.yml)'.format(repo_url) }}. Each holds MCUboot's
`zephyr.bin` and the application's `zephyr.signed.bin`. These images have limits:

- You need a GitHub account to download them. GitHub deletes them after a while, so keep your copy.
- They are signed with MCUboot's test key.
- The node's image has no Wi-Fi network: you type it on each node's pads before the node goes on its tray.
- There is no build directory, so `west flash` cannot write them. Write the two files with esptool, at the
  addresses in [What west flash writes](flash.md#what-west-flash-writes).
