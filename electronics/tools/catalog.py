"""Shared part catalogue: symbol, footprint and sourcing for every non-generic part.

LCSC numbers were checked against JLCPCB's live library (via the
@jlcpcb/mcp server, tools/jlc_mcp.py) on 2026-10-16.  Prices are USD per
piece at small quantity, used only for the BOM cost roll-up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import passives


@dataclass(frozen=True)
class Cat:
    lib_id: str
    footprint: str
    mpn: str
    manufacturer: str
    lcsc: str = ""
    price: float = 0.0
    basic: bool = False
    standard_only: bool = False   # JLC can only place it with Standard PCBA (not Economic)
    datasheet: str = ""
    description: str = ""
    alt: str = ""          # alternative sourcing notes
    hand_solder: bool = False     # through-hole, soldered by hand: kept out of the JLC BOM and CPL
    # 3D model replacing the footprint's own (missing from KiCad's library): (file in
    # electronics/lib/3dmodels, offset xyz mm (KiCad's model frame: y up), rotation xyz deg)
    model: tuple | None = None

    def fields(self) -> dict:
        f = {"MPN": self.mpn, "Manufacturer": self.manufacturer}
        if self.lcsc:
            f["LCSC"] = self.lcsc
        if self.alt:
            f["Alternative"] = self.alt
        return f


CAT = {
    "esp32s3": Cat("RF_Module:ESP32-S3-MINI-1", "RF_Module:ESP32-S2-MINI-1", "ESP32-S3-MINI-1-N8", "Espressif",
                   "C2913206", 4.72, standard_only=True,
                   # Espressif's own model; its corner sits at the module's bottom-left (KiCad footprint frame)
                   model=("ESP32-S3-MINI-1.step", (-7.7, -10.25, 0), (0, 0, 0)),
                   datasheet="https://www.espressif.com/sites/default/files/documentation/esp32-s3-mini-1_mini-1u_datasheet_en.pdf",
                   description="ESP32-S3 module, 8 MB flash, PCB antenna, USB OTG (full speed)"),
    "buck": Cat("bench:LMR51635", "Package_TO_SOT_SMD:TSOT-23-6", "LMR51635YDDCR", "Texas Instruments",
                "C45262770", 1.88, datasheet="https://www.ti.com/lit/ds/symlink/lmr51635.pdf",
                alt="LMR51635YFDDCR (C44750836): same, forced PWM, no spread spectrum",
                description="4.3–60 V 3.5 A synchronous buck, 1.1 MHz, PFM + spread spectrum"),
    "buck_l": Cat("Device:L", "Inductor_SMD:L_Changjiang_FXL0630", "FXL0630-3R3-M", "cjiang", "C167219", 0.11,
                  description="3.3 µH, 9.5 A sat, 8.5 A rms, 22 mΩ, molded"),
    "ldo": Cat("Regulator_Linear:AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "AMS1117-3.3", "AMS", "C6186",
               0.21, basic=True, description="3.3 V 1 A LDO"),
    "pfet": Cat("Transistor_FET:SUD50P06-15", "Package_TO_SOT_SMD:TO-252-2", "SUD50P06-15", "UMW / Vishay", "C7503186",
                0.36, alt="C7472883 (TECH PUBLIC), C141584 (Vishay)", description="P-MOSFET 60 V, reverse-polarity protection"),
    "zener12": Cat("Device:D_Zener", "Diode_SMD:D_SOD-123", "BZT52C12", "CJ", "C43491", 0.02,
                   description="12 V zener, P-FET gate clamp"),
    "tvs33": Cat("Device:D_Zener", "Diode_SMD:D_SMB", "SMBJ33A", "Brightking", "C78419", 0.07,
                 description="TVS 33 V stand-off, 600 W (unidirectional)"),
    "tvs33c": Cat("Device:D_Zener", "Diode_SMD:D_SMC", "SMCJ33A", "Littelfuse", "C224049", 0.33,
                  description="TVS 33 V stand-off, 1500 W (unidirectional)"),
    "cap100u50": Cat("Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10", "RVT1H101M0810", "Honor Elec", "C3352", 0.069,
                     description="100 µF 50 V aluminium electrolytic"),
    "cap220u50": Cat("Device:C_Polarized", "Capacitor_SMD:CP_Elec_10x10", "RVT1H221M1010", "Honor Elec", "C3358", 0.14,
                     description="220 µF 50 V aluminium electrolytic"),
    "mux": Cat("Interface_USB:FSUSB42MUX", "Package_SO:MSOP-10_3x3mm_P0.5mm", "FSUSB42MUX", "onsemi", "C11355", 0.31,
               datasheet="https://www.onsemi.com/pdf/datasheet/fsusb42-d.pdf", description="USB 2.0 HS 2:1 switch"),
    "or": Cat("74xGxx:74LVC1G32", "Package_TO_SOT_SMD:SOT-23-5", "SN74LVC1G32DBVR", "Texas Instruments", "C10096", 0.07,
              description="single 2-input OR"),
    "esd": Cat("Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "USBLC6-2SC6", "STMicroelectronics",
               "C7519", 0.18, alt="C2687116 (UMW clone)", description="USB ESD protection"),
    "usbc": Cat("Connector:USB_C_Receptacle_USB2.0_16P", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
                "TYPE-C-31-M-12", "Korean Hroparts", "C165948", 0.19, description="USB-C receptacle, USB 2.0, 16 pins"),
    "vbus_sw": Cat("bench:TPS2553DBV", "Package_TO_SOT_SMD:SOT-23-6", "TPS2553DBVR", "Texas Instruments", "C55266", 0.54,
                   datasheet="https://www.ti.com/lit/ds/symlink/tps2553.pdf",
                   description="adjustable current-limited power switch"),
    "ina226": Cat("Sensor_Energy:INA226", "Package_SO:TSSOP-10_3x3mm_P0.5mm", "INA226AIDGSR", "Texas Instruments",
                  "C49851", 0.75, datasheet="https://www.ti.com/lit/ds/symlink/ina226.pdf",
                  description="36 V current/voltage/power monitor, I2C"),
    # 1206 pads plus Kelvin sense pads (electronics/tools/footprints.py): pins 1/4 current, 2/3 sense
    "shunt50m": Cat("Device:R_Shunt", "bench:R_1206_3216Metric_Kelvin", "HoLR1206-1W-50mR-1%", "Milliohm", "C601102",
                    0.12, description="50 mΩ 1 % 1 W current shunt"),
    "rgb": Cat("LED:WS2812B-2020", "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm", "WS2812B-2020-V6", "Worldsemi",
               "C52917434", 0.09, standard_only=True, description="addressable RGB LED, 3.3–5.3 V",
               alt="WS2812C-2020-V6 (C55109522) is Economic-PCBA capable; check its pinout before swapping"),
    "button": Cat("Switch:SW_Push", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "TS-1187A-B-A-B", "XKB", "C318884",
                  0.02, basic=True, description="tactile switch 5.1 × 5.1 mm"),
    "slide": Cat("Switch:SW_SPDT", "Button_Switch_SMD:SW_SPDT_Shouhan_MSK12C02", "MSK12C02", "SHOU HAN", "C431540", 0.06,
                 description="SPDT slide switch, side actuated"),
    "nfet": Cat("Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002", "CJ", "C8545", 0.02, basic=True,
                description="N-MOSFET 60 V (open-drain AUX outputs)"),
    # connectors: JST PH (2 A) everywhere, JST VH (10 A) only where the whole rack's current comes in (hub input)
    "vh_h": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_VH_S2P-VH_1x02_P3.96mm_Horizontal", "S2P-VH(LF)(SN)",
                "JST", "C160355", 0.16, hand_solder=True, description="JST VH 2-pin, side entry, 10 A"),
    "vh_v": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_VH_B2P-VH_1x02_P3.96mm_Vertical", "B2P-VH(LF)(SN)",
                "JST", "C160315", 0.06, hand_solder=True, description="JST VH 2-pin, top entry, 10 A"),
    # bay node: surface-mount PH (JLC places them in the same reflow pass: no through-hole or hand soldering)
    "ph2": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal",
               "S2B-PH-SM4-TB(LF)(SN)", "JST", "C295747", 0.22, description="JST PH 2-pin, side entry, SMD, 2 A"),
    "ph2v": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
                "B2B-PH-K-S(LF)(SN)", "JST", "C131337", 0.04, hand_solder=True, description="JST PH 2-pin, top entry, 2 A"),
    "ph6": Cat("Connector_Generic:Conn_01x06", "Connector_JST:JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal",
               "S6B-PH-SM4-TB(LF)(SN)", "JST", "C265405", 0.39, description="JST PH 6-pin, side entry, SMD"),
    "pptc500": Cat("Device:Polyfuse_Small", "Fuse:Fuse_1206_3216Metric", "SMD1206P050TF", "RUILON", "C20799", 0.08,
                   description="PTC 0.5 A hold, 1206"),
    "efuse": Cat("Power_Management:TPS26600PWP",
                 "Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm",
                 "TPS26600PWPR", "Texas Instruments", "C544399", 1.54,
                 datasheet="https://www.ti.com/lit/ds/symlink/tps2660.pdf", description="4.2–60 V 2.23 A eFuse"),
    "led_g": Cat("Device:LED", "LED_SMD:LED_0805_2012Metric", "KT-0805G", "Hubei KENTO", "C2297", 0.02, basic=True,
                 description="green LED 0805"),
    "led_r": Cat("Device:LED", "LED_SMD:LED_0805_2012Metric", "NCD0805R1", "NationStar", "C84256", 0.01, basic=True,
                 description="red LED 0805"),
    # power hub v0.4: rack controller and CAN
    "can_xcvr": Cat("Interface_CAN_LIN:MCP2562-E-SN", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "TCAN1044AVDRQ1",
                    "Texas Instruments", "C3234993", 0.43, datasheet="https://www.ti.com/lit/ds/symlink/tcan1044av-q1.pdf",
                    description="CAN FD transceiver, VCC 5 V, VIO 1.8–5 V, bus pins ±58 V (MCP2562 pinout)"),
    "can_esd": Cat("Power_Protection:NUP2105L", "Package_TO_SOT_SMD:SOT-23", "PESD2CAN,215", "Nexperia", "C75176",
                   0.078, description="CAN bus ESD protection, 24 V stand-off"),
    "led_side_g": Cat("Device:LED", "LED_SMD:LED_Kingbright_KPA-3010_3x2x1mm", "KPA-3010CGCK", "Kingbright", "C598310",
                      0.24, description="green LED, side view 3 × 2 × 1 mm"),
    "led_side_r": Cat("Device:LED", "LED_SMD:LED_Kingbright_KPA-3010_3x2x1mm", "KPA-3010SURCK", "Kingbright",
                      "C4555382", 0.18, description="red LED, side view 3 × 2 × 1 mm"),
    "schottky": Cat("Device:D_Schottky", "Diode_SMD:D_SOD-123", "B5819W SL", "Changjing", "C8598", 0.03, basic=True,
                    description="40 V 1 A Schottky"),
    "bat54s": Cat("Diode:BAT54S", "Package_TO_SOT_SMD:SOT-23", "BAT54S", "hongjiacheng", "C7420333", 0.013,
                  description="dual Schottky in series: clamps a line to GND and +3V3"),
    "hdr2x8": Cat("Connector_Generic:Conn_02x08_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical",
                  "2x8 pin header 2.54 mm", "generic", "", 0.10, description="control header (DNP by default)"),
    # power hub v0.5: USB-C PD input (AP33772S sink, back-to-back NMOS switch, Kelvin shunt)
    "pd_sink": Cat("bench:AP33772S", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm", "AP33772SDKZ-13-FA02",
                   "Diodes Incorporated", "C50341643", 1.84,
                   datasheet="https://www.diodes.com/assets/Datasheets/AP33772S.pdf",
                   alt="LCSC stock was 0 on 2026-10-18: JLC global sourcing (DigiKey/Mouser) or a consigned reel",
                   description="USB PD 3.1 sink controller (EPR 28 V), I2C, VBUS NMOS gate drive, V/I/T telemetry"),
    "usbc5a": Cat("Connector:USB_C_Receptacle_USB2.0_16P",
                  "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "USB4105-GF-A-120", "GCT",
                  "C5184243", 0.91, description="USB-C receptacle, USB 2.0, 16 pins, 5 A on VBUS"),
    "nfet_pwr": Cat("Transistor_FET:Si4162DY", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "IRF7842TRPBF", "Infineon",
                    "C495809", 0.84, datasheet="https://www.infineon.com/dgdl/irf7842pbf.pdf",
                    description="N-MOSFET 40 V 18 A 5 mΩ, SO-8 (Si4162DY symbol: same S-S-S-G-D-D-D-D pinout)"),
    "shunt5m": Cat("Device:R_Shunt", "bench:R_1206_3216Metric_Kelvin", "HoLLR1206-1W-5mR-1%", "Milliohm", "C2988648",
                   0.055, description="5 mΩ 1 % 1 W current shunt"),
    "tvs30": Cat("Device:D_Zener", "Diode_SMD:D_SMA", "SMAJ30A", "MDD", "C113965", 0.044,
                 description="TVS 30 V stand-off, 400 W (unidirectional): above a 28 V EPR contract"),
    "ntc10k": Cat("Device:Thermistor_NTC", "Resistor_SMD:R_0603_1608Metric", "NCP18XH103F03RB", "Murata", "C13564",
                  0.05, description="NTC 10 kΩ B3380, 0603 (the AP33772S's default curve)"),
    "ldo_lp": Cat("Regulator_Linear:AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5", "AP2112K-3.3TRG1",
                  "Diodes Incorporated", "C51118", 0.17, description="3.3 V 600 mA LDO, 250 mV dropout"),
    "testpad": Cat("Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", "test pad", "-", "", 0.0),
    "hole": Cat("Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3 mounting hole", "-", "", 0.0),
}

HAND_SOLDER_LCSC = {c.lcsc for c in CAT.values() if c.hand_solder}
# MPN → (file, offset, rotation): see Cat.model and pcbgen.set_model()
MODELS = {c.mpn: c.model for c in CAT.values() if c.model}


def passive(kind: str, value: str, size: str) -> dict:
    """Fields for a generic R/C, LCSC basic part when one exists."""
    hit = passives.lookup(kind, value, size)
    if not hit:
        return {}
    return {"LCSC": hit["lcsc"], "MPN": hit["mpn"], "Manufacturer": hit["manufacturer"]}


def part(sheet, ref: str, key: str, conns: dict, value: str | None = None, pcb: dict | None = None, **kw):
    c = CAT[key]
    fields = c.fields()
    fields.update(kw.pop("fields", {}))
    return sheet.part(ref, c.lib_id, value or c.mpn, c.footprint, conns, fields=fields,
                      datasheet=c.datasheet, description=c.description, pcb=pcb or {}, **kw)


def R(sheet, ref, value, a, b, size="0603", pcb=None, **kw):
    return sheet.R(ref, value, a, b, size=size, fields={**passive("R", value, size), **kw.pop("fields", {})},
                   pcb=pcb or {}, **kw)


def C(sheet, ref, value, a, b, size="0603", pcb=None, **kw):
    return sheet.C(ref, value, a, b, size=size, fields={**passive("C", value, size), **kw.pop("fields", {})},
                   pcb=pcb or {}, **kw)
