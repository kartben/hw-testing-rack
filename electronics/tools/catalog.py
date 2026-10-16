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
                   datasheet="https://www.espressif.com/sites/default/files/documentation/esp32-s3-mini-1_mini-1u_datasheet_en.pdf",
                   description="ESP32-S3 module, 8 MB flash, PCB antenna, USB OTG (full speed)"),
    "buck": Cat("Regulator_Switching:TPS54360DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "TPS54360BDDAR",
                "Texas Instruments", "C524806", 0.75, datasheet="https://www.ti.com/lit/ds/symlink/tps54360b.pdf",
                description="60 V 3.5 A step-down converter"),
    "buck_l": Cat("Device:L", "Inductor_SMD:L_Changjiang_FXL1040", "FXL1040-100-M", "cjiang", "C475915", 0.26,
                  description="10 µH, 7.8 A sat, shielded"),
    "buck_d": Cat("Device:D_Schottky", "Diode_SMD:D_SMC", "B560C-13-F", "Diodes Inc", "C85100", 0.19,
                  description="Schottky 60 V 5 A (buck catch diode)"),
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
    "shunt50m": Cat("Device:R", "Resistor_SMD:R_1206_3216Metric", "HoLR1206-1W-50mR-1%", "Milliohm", "C601102", 0.12,
                    description="50 mΩ 1 % 1 W current shunt"),
    "rgb": Cat("LED:WS2812B-2020", "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm", "WS2812B-2020-V6", "Worldsemi",
               "C52917434", 0.09, standard_only=True, description="addressable RGB LED, 3.3–5.3 V",
               alt="WS2812C-2020-V6 (C55109522) is Economic-PCBA capable; check its pinout before swapping"),
    "button": Cat("Switch:SW_Push", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "TS-1187A-B-A-B", "XKB", "C318884",
                  0.02, basic=True, description="tactile switch 5.1 × 5.1 mm"),
    "slide": Cat("Switch:SW_SPDT", "Button_Switch_SMD:SW_SPDT_Shouhan_MSK12C02", "MSK12C02", "SHOU HAN", "C431540", 0.06,
                 description="SPDT slide switch, side actuated"),
    "nfet": Cat("Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002", "CJ", "C8545", 0.02, basic=True,
                description="N-MOSFET 60 V (open-drain AUX outputs)"),
    "vh_h": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_VH_S2P-VH_1x02_P3.96mm_Horizontal", "S2P-VH(LF)(SN)",
                "JST", "C160355", 0.16, description="JST VH 2-pin, side entry, 10 A"),
    "vh_v": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_VH_B2P-VH_1x02_P3.96mm_Vertical", "B2P-VH(LF)(SN)",
                "JST", "C160315", 0.06, description="JST VH 2-pin, top entry, 10 A"),
    "sh6": Cat("Connector_Generic_MountingPin:Conn_01x06_MountingPin",
               "Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal", "XY-SM06B-SRSS-TB", "XYECONN",
               "C56123098", 0.07, alt="JST SM06B-SRSS-TB(LF)(SN) C160405", description="JST-SH 6-pin side entry"),
    "ph2": Cat("Connector_Generic:Conn_01x02", "Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal",
               "S2B-PH-K-S(LF)(SN)", "JST", "C173752", 0.04, description="JST-PH 2-pin side entry"),
    "pptc500": Cat("Device:Polyfuse_Small", "Fuse:Fuse_1206_3216Metric", "SMD1206P050TF", "RUILON", "C20799", 0.08,
                   description="PTC 0.5 A hold, 1206"),
    "efuse": Cat("Power_Management:TPS26600PWP",
                 "Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm",
                 "TPS26600PWPR", "Texas Instruments", "C544399", 1.54,
                 datasheet="https://www.ti.com/lit/ds/symlink/tps2660.pdf", description="4.2–60 V 2.23 A eFuse"),
    "terminal": Cat("Connector:Screw_Terminal_01x02",
                    "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
                    "KF128-5.08-2P-AA", "Cixi Kefa", "C474952", 0.19, description="screw terminal 5.08 mm, 24 A"),
    "led_g": Cat("Device:LED", "LED_SMD:LED_0805_2012Metric", "KT-0805G", "Hubei KENTO", "C2297", 0.02, basic=True,
                 description="green LED 0805"),
    "led_r": Cat("Device:LED", "LED_SMD:LED_0805_2012Metric", "NCD0805R1", "NationStar", "C84256", 0.01, basic=True,
                 description="red LED 0805"),
    "hdr2x8": Cat("Connector_Generic:Conn_02x08_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical",
                  "2x8 pin header 2.54 mm", "generic", "", 0.10, description="control header (DNP by default)"),
    "testpad": Cat("Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm", "test pad", "-", "", 0.0),
    "hole": Cat("Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3 mounting hole", "-", "", 0.0),
}


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
