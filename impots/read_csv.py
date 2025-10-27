'''
Created on 16 avr. 2023

@author: MAO
'''
import sys
from datetime import datetime
import re

FIAT_EUR="EUR"

DEPOSIT_EUR_FEE=">depEUR"

TYPE_TRANSFER = "transfer"
TYPE_WITHDRAW = "withdrawal"

def DEBUG(x):
    if 1 : print(f"[DD]:{str(x)}")

def niceFloat(f):
    if abs(f) < 1e-20: return "0"
    if abs(f) < 1e-4: return f"{f:.2e}"
    if abs(f) < 1e-2: return f"{f:.4f}"
    if abs(f) < 10: return f"{f:.3f}" 
    return f"{f:.0f}" 

def actualAsset(asset):
    m = re.match(r'(.*[^0-9])[0-9]*[.][MS]?', asset)
    if m:
        return m.group(1)
    return asset

def rootCoin(c):
    return actualAsset(c.asset)

class BalanceError(Exception): 
    def __init__(self, msg, asset, txid, delta): 
        Exception(msg)
        self.msg=msg 
        self.txid = txid
        self.delta = delta
        self.asset=asset 
class CalcExcept(Exception): 
    def __init__(self, msg): Exception(msg) 
def ERROR(x):
    raise CalcExcept(str(x))

class AValue(object):
    ''' A value with an associated asset '''
    def __init__(self, asset:str, value):
        assert(type(asset) == str)
        self.asset,self.value = asset, value
    def __repr__(self): return f" {self.value} {self.asset}"
        
class Transaction(object):
    def __init__(self, src:AValue, dst:AValue, fees : [AValue], bal:[AValue], notice:str, date, txid):
        self.src, self.dst, self.fees, self.bal = src,dst,fees,bal
        self.notice, self.date, self.txid = notice, date, txid
    def __str__(self):
        fees=' + '.join([str(f) for f in self.fees])
        if fees: fees = f" (Fees : {fees})"
        return f"[{self.txid}] {self.src} => {self.dst} {fees}"
# 'time': '2020-12-30 21:39:54.7679'
def krakenTime(sTime):
    try:
        return datetime.strptime(sTime+ "00", '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        try:
            return datetime.strptime(sTime, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # print (f"sTime = {sTime}")# 
            ERROR(f"Cannot convert {sTime} to time")
    
class CSV_Gen():
    HEADERS = []
    HEADERS_OUT = []
    COINS=[]
    def titleMatches(self,title):  return title == self.HEADERS
    @staticmethod
    def eval(value, _title): return value
    def isCoinName(self,name): return name in self.COINS

class AirDrops(CSV_Gen):
    HEADERS = ["time","asset","amount","costEur","reason","note"]
    def __init__(self):
        CSV_Gen.__init__(self)
    def name(self): return "Airdrops"  
    @staticmethod
    def eval(value, title): 
        if title in ["amount", "costEur"]:
            try:value = float(value)
            except:
                ERROR (f"Invalid Float value for {title} : <{value}>")
        if title == "time": value = krakenTime(value)
        return value
    
    def toTransaction(self, line:list) -> Transaction:
        #Airdrops are assimilated to "deposit" at this level
        asset=line["asset"]
        line['refid']=f'{line["note"]:<.19}'
        src = AValue(asset=asset, value=0.0)
        dst = AValue(asset=asset, value=line["amount"])
        assert(line["reason"] in ["fork","deposit"])
        if line["reason"] == "deposit":
            # in case of "airdrop, this line intends at providing the actual cost of deposit (if non-euro).
            # This is counted as specific asset "DEPOSIT_EUR_FEE", but no other operation is used
            asset = DEPOSIT_EUR_FEE
            src = AValue(asset=asset, value=0.0)
            dst = AValue(asset=asset, value=line["costEur"])
        return Transaction(src=src, dst=dst, fees=[], bal=[], notice=line["reason"],
                           date=line['time'], txid=line['refid'])
    
class Ledger_Kraken(CSV_Gen):
    TRANSFERABLE={"ETH": "XETH"}
    class _Entry:
        def __init__(self, line:dict):
            self.line = line.copy()
            if (not self.txid) != (self.balance == None) and not self.balance == "auto":
                print("Mismatching entry / balance!", file =sys.stderr)
                print(f"While processing {line}", file =sys.stderr)
                ERROR ("Mismatching entry / balance!")
            if not self.txid:self.line["fee"] = 0
        def __repr__(self): return str(self.line)
        @property
        def refid(self): return self.line["refid"]
        @property
        def asset(self): return self.line["asset"]
        @property
        def amount(self): return self.line["amount"]
        @property
        def fee(self): return self.line["fee"]
        @property
        def hasFees(self): return abs(self.line["fee"]) > 1e-10
        @property
        def balance(self): return self.line["balance"]
        @property
        def txid(self): return self.line["txid"]
        @property
        def type(self): return self.line["type"]
    HEADERS = ["txid","refid","time","type","subtype","aclass","asset","amount","fee","balance"]
    HEADERS_OUT = ["aclass"]
    FLOAT_KEY=[]
    def __init__(self):
        CSV_Gen.__init__(self)
        self.pending = {} # {refid : _Entry}
        self.pendingtransfer = {}  # {asset: Transaction}.
        self.lastPending = None
    def name(self): return "Kraken-Ledger"  
    @staticmethod
    def eval(value, title): 
        if title == "balance" and not value: return None
        if title in ["amount", "fee", "balance"]:
            try:value = float(value)
            except:
                ERROR (f"Invalid Float value for {title} : <{value}>")
        if title == "time": value = krakenTime(value)
        return value
    
    def _isTransfer(self, entry):
        
        for _id, ref in self.pending.items():
            if ref.type != TYPE_TRANSFER: continue
                
            if rootCoin(ref) != rootCoin(entry) : continue
            
            val = (abs(ref.amount) + abs(entry.amount)) / 2
            if val < 1e-15: continue
            sum = ref.amount + entry.amount
            
            if abs(sum / val) > 1e-8 : ERROR(f"Invalid transfer refId={ref.refid} ({ref.amount} <=> {entry.amount} {rootCoin(entry)})")
            DEBUG(f"Found transfer for {niceFloat(ref.amount)} {rootCoin(entry)}")
            return ref
        return None
    
    def toTransaction(self, line:list) -> Transaction:
        if line["subtype"] == "spotfromfutures" and line["type"] == TYPE_TRANSFER :
            line["type"] = "reason" 
            
        if line["subtype"] == "migration" and line["type"] == "earn" :
            line["type"] = TYPE_TRANSFER
            line["balance"] = "auto"
            
        if (line["subtype"] == "reward" and line["type"] == "earn") or  line["type"] == "staking":
            # TODO : now Kraken may use the same name for different "Earn" sub-wallets (KAVA, KAVA.Earn/7, KAVA.EARN/21.. are all named "KAVA")
            line["balance"] = "auto"
            
        if line["txid"] == "LLFDLB-EM6Y3-G5VLTA":
            _dbg=1
            
        entry = Ledger_Kraken._Entry(line)
        # for breakpoint
        if line["refid"] == "LLFDLB-EM6Y3-G5VLTA":
            _dbg=1
            
        if entry.type in ["staking",  "earn", "margin"]:
            # Virtually create the line since it has not the same 'refid' (or no such line exists)
            lineS = line.copy()
            lineS["txid"] = ""
            lineS["balance"] = "auto"
            lineS["fee"] = 0.0
            self.pending[entry.refid] = Ledger_Kraken._Entry(lineS)

        elif entry.type == TYPE_WITHDRAW:
            # Virtually create the line (one line only for withdraw)
            lineS = line.copy()
            lineS["balance"] = "auto"
            lineS["fee"] = 0.0
            lineS["asset"] = FIAT_EUR
            lineS["amount"] = 0.0
            self.pending[entry.refid] = Ledger_Kraken._Entry(lineS)
            
        elif entry.type == "deposit":
            # Virtually create the line (one line only for deposit)
            lineS = line.copy()
            lineS["txid"] = ""
            lineS["balance"] = "auto"
            lineS["fee"] = 0.0
            self.pending[entry.refid] = Ledger_Kraken._Entry(lineS)
            
        elif entry.type == "rollover":
            # Discard previous line
            try:del self.pending[entry.refid]
            except:pass
            # Virtually create the line 
            lineS = line.copy()
            lineS["txid"] = ""
            lineS["balance"] = None
            lineS["fee"] = 0.0
            self.pending[entry.refid] = Ledger_Kraken._Entry(lineS)
        
        # Here we are trying to match 2 operations that actually are a single swp/exchange etc
        
        # Case 1 : 2 entries have the same "refid"
        entryRefId = entry.refid
        try:prevEntry = self.pending[entryRefId]
        except:prevEntry = None
        
        # Case 2 (Stake or transfer) : refId have change in 2025 and both line do not match
        # Match transfer from content on consecutive lines
        if not prevEntry:
            prevEntry = self._isTransfer(entry)
            if prevEntry:
                entryRefId = prevEntry.refid
        
        if prevEntry == None:
            self.pending[entryRefId] = entry
            self.lastPending = entryRefId
            return
        
        reason = entry.type
        # Use previous entry to compute transaction
        try:
            assert(prevEntry.refid == entryRefId or reason == TYPE_TRANSFER)
            src = AValue(asset=prevEntry.asset, value=prevEntry.amount)
            dst = AValue(asset=entry.asset, value=entry.amount)
            if reason in [TYPE_TRANSFER, TYPE_WITHDRAW] and dst.value < 0:
                src, dst= dst, src
        except:
            print(f"While processing {line}", file = sys.stderr)
            print(f"Previous entry was {prevEntry}", file = sys.stderr)
            ERROR (f"Invalid values ")
        
        if entry.type == "earn":
            reason = "earn"
        if not prevEntry.txid:
            # if value is negative, then swap source/dest
            if not src.value == dst.value:
                ERROR(f"Invalid amount : {src} / {dst}")
            if dst.value < 0:
                dst.value=0.0
            else:
                src.value=0.0
            
        # Compute Fees (Note that fees sign are inverted)
        fees=[AValue(asset=e.asset, value=-e.fee) for e in [entry, prevEntry] if e.hasFees]
        
        if src.value > 0 or dst.value < 0:
            print(f"While processing {line}", file = sys.stderr)
            print(f"Previous entry was {prevEntry}", file = sys.stderr)
            ERROR (f"{src} => {dst} , ")
        
        # Check special case when Two consecutive transaction cancel each other (withdrawal with neg fees on second)
        if (src.asset == dst.asset
            and abs(src.value + dst.value + sum([f.value for f in fees])) < 1e-7):
            # SRC = DST and no impact on total amount, just skip that operation
            DEBUG(f"Skipping {entry.txid}/{prevEntry.txid} because it is a NULL operation")
            res = None
        else:
            bal=[AValue(asset=e.asset, value=e.balance) for e in [entry, prevEntry] if e.balance != None]
            
            res = Transaction(src=src, dst=dst, fees=fees, bal=bal, notice=reason,
                               date=line['time'], txid=line['txid'])
            
            if 0:
                # note : some staking operations are sometime shown as 2 distinct transactions which causes the loss of
                # actual transaction context. In that case, the 2 transactions are consolidated in a single one
                
                try:
                    res = self.consolidateWithLastTx(res)
                except Exception as E:
                    print(f"Processing of {entry} failed")
                    raise E
        # print (res)
        del self.pending[entryRefId]
        
        return res
    def consolidateWithLastTx(self, trans:Transaction) -> Transaction:
        # Find if a pending transfer of the same asset exists
        
        name = actualAsset(trans.src.asset)
        nameIni=name[:]

        # Some Crypto are renamed, which implies a "transfer" with 2 different names (e.g. XETH => ETH)
        # Always use the same alternate name
        if name in Ledger_Kraken.TRANSFERABLE:
            name = Ledger_Kraken.TRANSFERABLE[name]
        
        if trans.notice == TYPE_TRANSFER:
            assert(rootCoin(trans.src) == rootCoin(trans.dst))
        elif trans.notice == "withdrawal" :
            if not (trans.src.asset == trans.dst.asset
                    and trans.src.value + trans.dst.value == 0):
                return trans
            else:
                DEBUG (f"Add withdrawal pending({name})")
        else:return trans
        
        if not name in self.pendingtransfer:    
            self.pendingtransfer[name] = trans
            DEBUG (f"Add transfer pending({name}):{self.pendingtransfer[name]}")
            return None
        
        prev = self.pendingtransfer[name]
        
        
        # Create a virtual transaction holding the 2 sub-transactions
        if abs(trans.src.value) > 1e-8:
            if abs(trans.dst.value) > 1e-8:
                ERROR(f"Balance issue {trans.src} => {trans.dst}")
            src = AValue(asset=trans.src.asset, value=trans.src.value)
            dst = AValue(asset=prev.dst.asset, value=prev.dst.value)
        else:
            assert(abs(trans.dst.value) > 1e-8)
            src = AValue(asset=prev.src.asset, value=prev.src.value)
            dst = AValue(asset=trans.dst.asset, value=trans.dst.value)
        
        del self.pendingtransfer[name]
        res = Transaction(src=src, dst=dst,
                           fees=trans.fees+prev.fees,
                           notice="staking",
                           bal=trans.bal + prev.bal,
                           date=trans.date, txid=trans.txid)
        # print(res)
        return res
        
        
class CSV_Kraken(CSV_Gen):
    HEADERS = ["txid", "ordertxid", "pair", "time", "type", "ordertype", "price", "cost", "fee", "vol", "margin", "misc", "ledgers"]
    HEADERS_OUT = ["ordertxid", "ordertype", "margin", "ledgers"]

    def __init__(self): CSV_Gen.__init__(self)
    def name(self): return "Kraken"  
    @staticmethod
    def eval(value, title): 
        if title in ["price", "cost", "fee", "vol", "margin"]:
            try:value = float(value)
            except:
                ERROR (f"Invalid Float value : <{value}>")
        if title == "time": value = krakenTime(value)
        return value
    def toTransaction(self, line:list) -> Transaction:
        pairName = line['pair']
        try:
            source , dest = pairName.split("/")
            if not source or not dest:
                raise Exception("")
        
        except Exception as E:
            ERROR(f"Failed to recognize pair {pairName} ({E})")
        if source == dest : Error(f"Invalid pair {pairName}")
        DEBUG(f"Detected pair: {(source,dest)}")
        try:
            tType = line['type']
        except:  ERROR (f"Missing 'type' section for transaction {line}")

        amntSrc, amntDest = line['vol'], line['cost']
        currFee = dest
        amntFee = line['fee']
        if tType == "sell":
            pass
        elif tType =="buy":
            source, dest = dest,source
            amntSrc, amntDest = amntDest, amntSrc
            pass
        else:ERROR (f"Invalid 'buy'/'sell' type")

        misc =  line["misc"]
        price = line['price']
        # if misc and misc not in ["initiated", "direct"] : print (misc)
        if "revFee" in misc:
            # Fees are to be converted on source!
            currFee = source
            amntFee = amntFee / price
        
        return Transaction(src=AValue(asset = source,  value = amntSrc),
                           dst=AValue(asset = dest, value = amntDest),
                           fees=[AValue(asset = currFee, value = amntFee)])
    
class Operation(object):
    def __init__(self, d : dict):
        self.__dict = dict
    def __getitem__(self, v):
        return self.__dict[v]
        
        
class ListToDictConverter():
    def __init__(self, csv:CSV_Gen):
        self.csv=csv
    def __call__(self, line:list):
        if len(line) == len (self.csv.HEADERS):
            # print (f"OK => {line}")
            return {self.csv.HEADERS[i]:self.csv.eval(line[i],self.csv.HEADERS[i]) for i in range (len(line)) if self.csv.HEADERS[i] not in self.csv.HEADERS_OUT}
        print ("Mismatching line (%s)"%line, file = sys.stderr)
        print (f"Expected {len (self.csv.HEADERS)} elements")
        print (f"Found {len(line)} elements")
        ERROR("Mismatching line (%s)"%line)
            
class CSV_File(object):

    def __init__(self, filename):
        '''
        Constructor
        '''
        self.__lines=[]
        self.__sourceSite = ""
        try:
            self.__nbLines = -1 # first line is a title
            print(f"[II] Opening file {filename}")
            with open(filename) as f:
                for l in f.readlines():
                    self.__ingest (l.strip())
                
        except Exception as e:
            ERROR(f"[EE] Failed to open/read {filename}:{str(e)}")
            raise e
        self.preview()
        self.autoDetect()
        conv = ListToDictConverter(self.__sourceSite)
        self.datas=[conv(l) for l in self.lines()]
        
    def sourceSite(self):return self.__sourceSite
    def __ingest(self, line):
        try:
            if not line: return
            self.__nbLines += 1
            # There may be commas inside quotes that must be ignored. Split must be done manually
            # self.__lines.append(line.split(","))
            res = []
            word=''
            isString=False
            for c in line:
                if c == '"': isString = not isString
                else:
                    if not isString:
                        if c in ';,':
                            res.append(word.strip())
                            word = ""
                        elif c in "#": break# skip until EOL
                        else:word += c
                    else:word += c
            res.append(word.strip())
            self.__lines.append(res)
        except:
            print (f"Context:\n{line}")
            ERROR (f"Invalid input line (L={self.nbLines})")
    def title(self):
        if (self.__lines): return self.__lines[0]
        ERROR ("Empty document")
    def lines(self): 
        if len(self.__lines) < 1: return []
        return self.__lines[1:]
    def preview(self):
        print (" ".join(["%-30s" % l for l in self.title()]))
        print ("\n".join(["%-30s" % f for f in self.__lines[:10]]))
        # print ("\n".join(["%-30s" % f for f in self.__lines[-100:]]))
        print("Total : %d operations "% (self.__nbLines))
            
    def autoDetect(self):
        '''
            Detects the origin of file (Kraken...)
        '''
        for cType in [CSV_Kraken, Ledger_Kraken, AirDrops]:
            csv= cType()
            if csv.titleMatches(self.title()):
                print (f"Detected '{csv.name()}' as source site")
                self.__sourceSite = csv
                return
            
        ERROR ("Could not detect source site")
        