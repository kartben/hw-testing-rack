<!-- Contributor documentation, kept in the repository: it is not part of the published site, which is the
     user's manual (docs/STYLE.md). -->

# Work on the firmware

The bay node and the power hub run two Zephyr applications for the ESP32-S3, both at version 0.5.0, which share
the rack bus protocol, their drivers and their web tooling. Their tests run on a PC under native_sim, and both
applications run on off-the-shelf ESP32-S3 boards that stand in for the PCBs.

## Two applications and a common part

| Folder | What it holds |
|---|---|
| [firmware/bay-node](../../firmware/bay-node) | the node: USB host and USB/IP, the DATA board's ports, the console, the wires and the analyzer, the camera, its page and API |
| [firmware/power-hub](../../firmware/power-hub) | the hub: the USB PD contract, the rows, the power budget, the rack bus master, its page and API |
| [firmware/common](../../firmware/common) | the rack bus protocol, the CH224A and CH446Q drivers, Wi-Fi, hostname and DNS-SD, the pages' CSS and helpers, xterm.js, the development server and the screenshot tooling |
| [firmware/boards/hwtr](../../firmware/boards/hwtr), [firmware/dts](../../firmware/dts) | the board definitions `bay_node/esp32s3/procpu` and `power_hub/esp32s3/procpu`, and the `hwtr,*` and `wch,ch224a` bindings |
| [zephyr/](../../zephyr) | `module.yml`, which makes the repository a Zephyr module, and the patches carried on Zephyr |
| [firmware/tools](../../firmware/tools), [firmware/spikes](../../firmware/spikes) | the pin-map check; two throw-away programs ([Design notes, studies and reviews](notes.md#spikes)) |

The protocol between them is [rack-protocol.md](../rack-protocol.md). Each README lists its sources file by
file: [firmware/README.md](../../firmware/README.md),
[firmware/power-hub/README.md](../../firmware/power-hub/README.md). One node image serves a DATA ×4 and a
DATA ×6: `data-x4.dtsi` and `data-x6.dtsi` are added by the application, not by the board, so MCUboot never
pulls in their drivers, and `src/ports.c` tells the two boards apart at each probe
([multi-dut-node.md](../multi-dut-node.md#which-board-data-4-or-data-6)).

What the firmware does not do yet, and what has not run on a v1.0 PCB, is one list:
[firmware.md › Open items](../firmware.md#open-items). What a user meets of it:
[Known issues of firmware 0.5](../reference/known-limitations.md#known-issues-of-firmware-05).

## The Zephyr pin and the carried patches

[firmware/west.yml](../../firmware/west.yml) pins Zephyr to a commit of main of 2026-10-16
(`3f7ae83e0e7c`), with five modules: `hal_espressif`, `mbedtls`, `tf-psa-crypto`, `mcuboot`, `lvgl`. Bump it on
purpose and run `west update` again: the USB host stack still moves fast. The workspace itself, and the two
builds: [Build or download the firmware](../build/get-the-firmware.md).

`west patch apply` puts eight patches on top, listed in [zephyr/patches.yml](../../zephyr/patches.yml), until
Zephyr has them:

| Patch | What it changes |
|---|---|
| `usbip-removal-and-busid.patch` | USB/IP: bus IDs by port (`1-1.3` behind port 3 of a hub), no hubs on offer, a device that goes ends its session, read-ahead on serial converters, large mass storage requests in segments |
| `uhc-dwc2-channels.patch` | the DWC2 host: the ESP32-S3's 8 channels shared between pending transfers, endpoint state by device address, transfers longer than the channel counters |
| `usbh-hub-port-reset.patch` | the hub class: debounce before a port reset, a port whose resets all failed reset only on a new connection |
| `usbip-tcp-nodelay.patch` | USB/IP: `TCP_NODELAY`, a completion's data sent without waiting for its header's acknowledgement |
| `net-sockets-recv-window.patch` | sockets: the receive window opens as `recv()` consumes the data |
| `wifi-esp32-link-hold.patch` | ESP32 Wi-Fi: a lost link logged with its reason, and held while the station reconnects |
| `net-tcp-keep-mss.patch` | TCP: a connection keeps its negotiated MSS after an ACK with SACK blocks |
| `shell-telnet-send-work.patch` | the telnet shell: a failed deferred send no longer stops the system work queue |

`west patch list` shows them and `west patch reverse` takes them out. A patch file is a series of Zephyr commits
made with `git format-patch --stdout`, kept byte for byte; after regenerating one, update its `sha256sum` in
`patches.yml`:

```console
$ sha256sum zephyr/patches/zephyr/usbip-tcp-nodelay.patch
```

Each entry's comment says whether a pull request upstream carries it, and when to drop the file. What the node
still needs from Zephyr: [multi-dut-node.md › What Zephyr needs](../multi-dut-node.md#what-zephyr-needs-upstream).

The repository is a Zephyr module, so a plain build also works from another workspace at a recent main, with the
`hal_espressif` blobs fetched: each application adds the module itself. Sysbuild needs it known before the
application:

```console
$ west build --sysbuild -b bay_node/esp32s3/procpu path/to/hw-testing-rack/firmware/bay-node -- -DEXTRA_ZEPHYR_MODULES=path/to/hw-testing-rack
```

## Run it without the PCBs

Two development servers serve the node's and the hub's pages and APIs from Python, in the firmware's JSON
shape ([where the node's differs](../reference/node-api.md#routes-and-the-right-each-needs)), with hooks under
`/dev/` that make faults happen. The hub's needs the standard library only, the node's PyYAML too (Pillow,
optional, for its camera). The node's camera takes port 8767, the hub's default, so the hub gets another:

```console
$ python firmware/bay-node/web/dev_server.py --ports 4
$ python firmware/power-hub/web/dev_server.py 8770
```

A session against them, with `bayctl` and the hooks: [Try it without hardware](../plan/try-it-without-hardware.md).

The node's console, web server and access control also run as Zephyr code on native_sim, with Zephyr's shell
sample as the board on its AUX UART (Linux, or the Zephyr build image in Docker):

```console
$ python3 firmware/bay-node/tests/console_sim/run.py --workspace <west workspace> --build <dir>
```

It serves the page on port 80 and RFC 2217 on 4001 of `localhost`.

The node's page is `firmware/bay-node/web/index.html`, served gzipped from the node's flash; the hub's is
`firmware/power-hub/web/index.html`. Both share `rack.css` and `rack.mjs` from `firmware/common/web/`. Work on a
page against its development server, then regenerate this site's screenshots from the simulation:
[Regenerate the site, the viewer, the renders, the drawings](regenerate.md#screenshots-and-the-console-screencast).

## On a stand-in board

| Board target | Application | What it can test |
|---|---|---|
| `esp32s3_devkitc/esp32s3/procpu` | node | the node's own GPIO map on a DevKitC-1; the board on its USB port through an OTG adapter; the camera, with an Arducam Mega on jumpers |
| `m5stack_stamps3/esp32s3/procpu` | node | the console and the network side, no USB host: its USB-C carries the node's shell and logs, the AUX UART is on G1 (TX) and G2 (RX), RESET and BOOT on G4 and G5 ([the overlay](../../firmware/bay-node/boards/m5stack_stamps3_procpu.overlay)); `bay aux loopback on` loops the AUX UART back |
| `m5stack_cores3/esp32s3/procpu` | node, hub | USB host and USB/IP on its USB-C, the board's power switched; the hub's CH224A on a breakout |
| `xiao_esp32s3/esp32s3/procpu` | node, hub | the node's octal PSRAM, its buttons; the hub's IMON, so the shedding |

All four build with `--sysbuild`, as the PCBs' targets do, and are in the CI matrix. At boot the node's USB host
takes the S3's only PHY and the PC loses the port. How each board is flashed again, the wiring, the bench plans
and what the XIAO measured: [bench.md](../bench.md).

## Tests

CI ([firmware.yml](../../.github/workflows/firmware.yml)) builds 21 images with warnings as errors and runs every
native_sim one. In a workspace where `west patch apply` has run, on Linux, a ztest suite is built and run as CI
does it:

```console
$ west build -b native_sim/native/64 -d build hw-testing-rack/firmware/common/tests/rack_bus
$ build/zephyr/zephyr.exe
```

It passes when the run prints `PROJECT EXECUTION SUCCESSFUL`. The suites, each with its `testcase.yaml`:

| Suite | What it tests |
|---|---|
| `firmware/common/tests/rack_bus` | the rack bus on a simulated rack, hub and nodes: enumeration, reboots, lost nodes, retries |
| `firmware/common/tests/update` | firmware updates: the image parser, the upload into slot 1, the trial and the rollback |
| `firmware/common/tests/usbh_hub` | the patched hub class against a made-up hub whose ports fail to reset |
| `firmware/common/tests/dnssd` | the DNS-SD records, kept in step with what listens |
| `firmware/common/tests/ch446q` | the CH446Q driver against emulated chips |
| `firmware/bay-node/tests/ports` | a DATA ×4 and a DATA ×6 behind the node: admission, faults, shedding, RESET and BOOT |
| `firmware/bay-node/tests/data_lead` | node v1.0's DATA lead and its eFuse's power-on rule |
| `firmware/bay-node/tests/wires` | the pin matrix with the real drivers, against two emulated CH446Q |
| `firmware/bay-node/tests/coproc` | the co-processor's image, uploaded into its partition |
| `firmware/bay-node/tests/analyzer` | the analyzer relayed to the bay's page, against an emulated analyzer |
| `firmware/power-hub/tests/budget` | the hub's power budget, with made-up contracts and row currents |

The same eleven, through twister (worked out from the `testcase.yaml` files; CI does not run twister, and nobody
has run this):

```console
$ west twister -T hw-testing-rack/firmware -p native_sim/native/64
```

Five more tests are Python scripts. Two drive a native_sim application: the patched USB/IP service, and the
node's access control, which needs root because the node's web server binds port 80. CI builds each
application as above, then:

```console
$ west build -b native_sim/native/64 -d build hw-testing-rack/firmware/common/tests/usbip
$ python3 hw-testing-rack/firmware/common/tests/usbip/test_usbip.py --exe build/zephyr/zephyr.exe
$ west build -b native_sim/native/64 -d build-access hw-testing-rack/firmware/bay-node/tests/console_sim
$ sudo python3 hw-testing-rack/firmware/bay-node/tests/console_sim/test_access.py --exe build-access/zephyr/zephyr.exe
```

Three run on the host, from the top of a checkout, each building its C source with a C compiler (`CC`, gcc by
default): the RFC 2217 server against pyserial's client, the access rules' SHA-256 and HMAC against Python's,
and the camera's JPEG end finder:

```console
$ pip install pyserial
$ python firmware/bay-node/tests/rfc2217/test_rfc2217.py
$ python3 firmware/bay-node/tests/acl/test_acl.py
$ python3 firmware/bay-node/tests/jpeg/test_jpeg.py
```

The logic analyzer's page has its own tests, under Node 22:

```console
$ node --test "firmware/common/web/analyzer/test/*.test.mjs"
```

## The pin-map check

```console
$ python3 firmware/tools/check_pinmap.py
```

It checks the module's pins in each PCB's `design.py` against the `## Pin map` table of the firmware README and
against the board's devicetree, for the node and the hub. It needs the standard library only, prints
`pin map OK: …` for each, and exits 1 on a mismatch. It finds each table by its heading: keep the heading exactly
`## Pin map`, at level 2, and the first cell of each row `IO<n>` or `<name> (IO<n>)`. The PCB pages of this site
include those two tables between their `site:pin-map` markers, so the tables stay in the READMEs.
