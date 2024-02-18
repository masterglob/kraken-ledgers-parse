# -*- coding: utf-8 -*-

from read_csv import actualAsset

class JTransaction(object):
    ShowMeanV=True
    ShowAmount=False
    def __init__(self, trans, tType, asset, value):
        self.trans = trans
        self.tType=tType
        self.asset=actualAsset(asset)
        if value is None:
            self.value=None
        elif abs(value) < 1e-3:
            self.value=f"{value:.3e}"
        elif abs(value) < 1e+3:
            self.value=f"{value:.2f}"
        else:
            self.value=f"{value:.0f}"
    def assetMatches(self, asset):
        return (asset.upper() == self.asset)
    def __repr__(self):
        return f"[{self.tType} {self.asset} {self.value}]"
    def __str__(self):
        p=""
        if JTransaction.ShowAmount:
            p = p + f" Bal" + ",".join(str(bal) for bal in self.trans.bal)
            
        if JTransaction.ShowMeanV:
            if self.tType == "T" and self.value is not None: # Transaction
                p = p+ f" MeanValue({self.value} Eur/{self.asset})"
        return f"[{self.tType} Tx={self.trans} {p}"
        
class Journal(object):


    def __init__(self):
        self.allAssets= set()
        self.events = []
    
    def addAsset(self, asset):
        self.allAssets.add(asset.upper().replace(".S",""))
    def deposit(self, trans, asset, value):
        self.addAsset(asset)
        self.events.append(JTransaction(trans, "D",asset, value))
    def withdrawal(self, trans, asset, value):
        self.addAsset(asset)
        self.events.append(JTransaction(trans, "W",asset, value))
    def transaction(self, trans, assetS, assetD, value):
        self.addAsset(assetS)
        self.addAsset(assetD)
        self.events.append(JTransaction(trans, "T",assetD, value))
        if assetS != assetD:
            self.events.append(JTransaction(trans, "T",assetS, None))

    def getByType(self, tType):
        return [e for e in self.events if e.tType == tType]

    def getByAsset(self, asset):
        return [e for e in self.events if e.assetMatches(asset)]
    