from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QGridLayout, QPushButton, QCheckBox, QHBoxLayout, QInputDialog)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QDoubleValidator

try:
    from i18n import _
    import utils_ui
    import utils
except Exception:
    from COMTool.i18n import _
    from COMTool import utils_ui
    from COMTool import utils

import pyqtgraph as pg

from struct import unpack, pack

class Gragh_Widget_Base(QWidget):
    def __init__(self, parent=None, hintSignal = lambda type, title, msg:None, rmCallback=lambda widget:None, send=lambda x:None, config=None, defaultConfig=None):
        QWidget.__init__(self, parent)
        self.hintSignal = hintSignal
        self.rmCallback = rmCallback
        self.send = send
        if config is None:
            config = {}
        if not defaultConfig:
            defaultConfig = {}
        self.config = config
        for k in defaultConfig:
            if not k in self.config:
                self.config[k] = defaultConfig[k]

    def onData(self, data:bytes):
        pass


class Gragh_Plot(Gragh_Widget_Base):
    updateSignal = pyqtSignal(dict)
    id = "plot"
    def __init__(self, parent=None, hintSignal = lambda type, title, msg:None, rmCallback=lambda widget:None, send=lambda x:None, config=None):
        default = {
            "xRange": 10,
            "xRangeEnable": True,
            "header": "\\xAA\\xCC\\xEE\\xBB"
        }
        super().__init__(parent, hintSignal=hintSignal, rmCallback=rmCallback, send = send, config = config, defaultConfig=default)
        self.headerBytes = utils.str_to_bytes(self.config["header"], escape=True, encoding="utf-8")
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.plotWin = pg.GraphicsLayoutWidget()
        self.plotWin.setMinimumHeight(200)
        pg.setConfigOptions(antialias=True)
        rmBtn = QPushButton(_("Remove"))
        rangeLabel = QLabel(_("Range:"))
        rangeConf = QLineEdit(str(self.config["xRange"]))
        rangeEnable = QCheckBox(_("Enable"))
        rangeEnable.setChecked(self.config["xRangeEnable"])
        headerLabel = QLabel(_("Header:"))
        headerConf = QLineEdit(self.config["header"])
        headerBtn = QPushButton(_("Set"))
        hint = _("Protocol: header + 1Byte name length + name + 8Bytes x(double) + 8Bytes y(double) + 1Byte sum")
        headerConf.setToolTip(hint)
        headerLabel.setToolTip(hint)
        headerBtn.setToolTip(hint)
        validator = QDoubleValidator()
        rangeConf.setValidator(validator)
        self.layout.addWidget(self.plotWin, 0, 0, 1, 3)
        self.layout.addWidget(rmBtn, 1, 0, 1, 1)
        self.layout.addWidget(rangeLabel, 2, 0, 1, 1)
        self.layout.addWidget(rangeConf, 2, 1, 1, 1)
        self.layout.addWidget(rangeEnable, 2, 2, 1, 1)
        self.layout.addWidget(headerLabel, 3, 0, 1, 1)
        self.layout.addWidget(headerConf, 3, 1, 1, 1)
        self.layout.addWidget(headerBtn, 3, 2, 1, 1)
        self.resize(600, 400)
        self.p = self.plotWin.addPlot(colspan=2)
        # self.p.setLabel('bottom', 'x', '')
        self.p.addLegend()
        self.p.setXRange(0, self.config["xRange"])
        self.updateSignal.connect(self.update)
        self.curves = {}
        self.rawData = b''
        self.data = {}
        self.builtinColors = [
                "#BD4B4B",
                "#3BB273",
                "#FFFFFA",
                "#307473",
                "#3C6997",
                "#746D75",
                "#228CDB",
                "#824C71",
                "#7768AE",
                "#DC6BAD",
                "#607d8b",
                "#F18701",
                "#912F40",
                "#414288",
                "#ED4D6E",
                "#FFD29D",
                "#B56576",
                "#503B31",
                "#93E1D8",
                "#596157",
            ]
        self.notUsedColors = self.builtinColors.copy()
        self.colors = {

        }
        rangeConf.textChanged.connect(self.setRange)
        rangeEnable.clicked.connect(lambda: self.setEnableRange(rangeEnable.isChecked()))
        headerBtn.clicked.connect(lambda: self.setHeader(headerConf.text()))
        rmBtn.clicked.connect( self.remove)

    def remove(self):
        self.rmCallback(self)

    def setRange(self, text):
        if text:
            self.config["xRange"] = float(text)

    def setEnableRange(self, en):
        self.config["xRangeEnable"] = en

    def setHeader(self, text):
        if text:
            try:
                textBytes = utils.str_to_bytes(text, escape=True, encoding="utf-8")
                self.config["header"] = text
                self.headerBytes = textBytes
            except Exception:
                self.hintSignal.emit("error", _("Error"), _("Format error"))

    def decodeData(self, data: bytes):
        '''
            @data bytes, protocol:
                         |    header(4B)    | line name len(1B) | line name | x(8B) | y(8B) | sum(1B) |
                         | AA CC EE BB      | 1~255             |  roll     | double | double | uint8   |
            @return dict {
                "name": {
                    "x": [],
                    "y": []
                }
            }
        '''
        # append data
        self.rawData += data
        # find header
        header = self.headerBytes
        idx = self.rawData.find(header)
        if idx < 0:
            return self.data
        self.rawData = self.rawData[idx:]
        # check data length
        nameLen = unpack("B", self.rawData[len(header) : len(header) + 1])[0]
        frameLen = len(header) + nameLen + 18  # 5 + nameLen + 16 + 1
        if len(self.rawData) < frameLen:
            return self.data
        # get data
        frame = self.rawData[:frameLen]
        self.rawData = self.rawData[frameLen:]
        _sum = frame[-1]
        # check sum
        if _sum != sum(frame[:frameLen - 1]) % 256:
            return self.data
        name = frame[len(header) + 1 : len(header) + 1 + nameLen].decode("utf-8")
        x = unpack("d", frame[-17:-9])[0]
        y = unpack("d", frame[-9:-1])[0]
        if not name in self.data:
            self.data[name] = {
                "x": [x],
                "y": [y]
            }
        else:
            self.data[name]["x"].append(x)
            self.data[name]["y"].append(y)
        return self.data

    def pickColor(self, name:str):
        if name in self.colors:
            return self.colors[name]
        else:
            if not self.notUsedColors:
                self.notUsedColors = self.builtinColors.copy()
            color = self.notUsedColors.pop(0)
            self.colors[name] = color
            return color

    def update(self, data:dict):
        for k, v in data.items():
            if not k in self.curves:
                print("add curve:", k)
                color = self.pickColor(k)
                self.colors[k] = color
                self.curves[k] = self.p.plot(pen=pg.mkPen(color=color, width=2),
                                            name=k,)
                                            # symbolBrush=color, symbolPen='w', symbol='o', symbolSize=1)
            if self.config["xRangeEnable"] and self.config["xRange"] > 0:
                self.p.setXRange(v["x"][-1] - self.config["xRange"], v["x"][-1])
            self.curves[k].setData(x=v["x"], y=v["y"])

    def onData(self, data: bytes):
        data = self.decodeData(data)
        self.updateSignal.emit(data)


class Gragh_Button(Gragh_Widget_Base):
    class Button(QWidget):
        def __init__(self, rmCallback, addCallback, clickCallback, changeCallback, name="hello") -> None:
            super().__init__()
            self.rmCallback = rmCallback
            self.changeCallback = changeCallback
            layout = QHBoxLayout()
            layoutSetting = QVBoxLayout()
            self.setLayout(layout)
            self.button = QPushButton(name)
            self.button.setProperty("class", "bigBtn")
            layout.addLayout(layoutSetting)
            layout.addWidget(self.button)
            self.addBtn = QPushButton()
            self.rmBtn = QPushButton()
            self.editBtn = QPushButton()
            self.addBtn.setProperty("class", "smallBtn3")
            self.rmBtn.setProperty("class", "smallBtn3")
            self.editBtn.setProperty("class", "smallBtn3")
            utils_ui.setButtonIcon(self.addBtn, "fa.plus")
            utils_ui.setButtonIcon(self.rmBtn, "fa.minus")
            utils_ui.setButtonIcon(self.editBtn, "fa.edit")
            layoutSetting.addWidget(self.rmBtn)
            layoutSetting.addWidget(self.addBtn)
            layoutSetting.addWidget(self.editBtn)
            layoutSetting.addStretch()
            self.rmBtn.clicked.connect(self.onRm)
            self.addBtn.clicked.connect(lambda:addCallback(self))
            self.editBtn.clicked.connect(self.editButton)
            self.button.clicked.connect(lambda:clickCallback(self, utils.str_to_bytes(self.getText(), escape=True, encoding="utf-8")))

        def getText(self):
            return self.button.text()

        def onRm(self):
            utils_ui.clearButtonIcon(self.addBtn)
            utils_ui.clearButtonIcon(self.rmBtn)
            utils_ui.clearButtonIcon(self.editBtn)
            self.rmCallback(self)

        def editButton(self):
            v, ok = QInputDialog.getText(self, _("Set button name"), _("Name:"), QLineEdit.Normal, self.button.text())
            if v:
                self.button.setText(v)
                self.changeCallback(self)


    id = "button"
    def __init__(self, parent=None, hintSignal=lambda type, title, msg: None, rmCallback=lambda widget: None, send=lambda x: None, config=None):
        default = {
            "items": []
        }
        super().__init__(parent, hintSignal, rmCallback, send, config, default)
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        if not self.config["items"]:
            button = Gragh_Button.Button(self.onRm, self.onAdd, self.onClick, self.onChange)
            self.layout.addWidget(button)
            self.buttons = [button]
            self.config["items"] = [button.getText()]
        else:
            self.buttons = []
            for item in self.config["items"]:
                button = Gragh_Button.Button(self.onRm, self.onAdd, self.onClick, self.onChange, name=item)
                self.layout.addWidget(button)
                self.buttons.append(button)

    def onRm(self, widget):
        '''
            @widget Gragh_Button.Button
        '''
        self.buttons.remove(widget)
        widget.setParent(None)
        if not self.buttons:
            self.rmCallback(self)

    def onAdd(self, widget):
        '''
            @widget Gragh_Button.Button
        '''
        button = Gragh_Button.Button(self.onRm, self.onAdd, self.onClick, self.onChange)
        self.layout.addWidget(button)
        self.buttons.append(button)
        self.config["items"].append(button.getText())

    def onClick(self, widget, data:bytes):
        self.send(data)

    def onChange(self, widget):
        self.config["items"][self.buttons.index(widget)] = widget.getText()


graghWidgets = {
    Gragh_Plot.id: Gragh_Plot,
    Gragh_Button.id: Gragh_Button
}

