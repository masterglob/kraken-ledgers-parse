'''
Created on 16 avr. 2023

@author: MAO
'''
import sys
import os

from read_csv import CalcExcept, BalanceError
from calculator import GainCalculcator

def printE(s):print (s, file = sys.stderr)

if __name__ == '__main__':
    try:
        DO_DEBUG=0
        
        YEAR=2022
        gains = GainCalculcator()
        gains.inject(f'files/deposits{YEAR}.csv')
        gains.inject(f'files/ledgers{YEAR}.csv')
        
        outDir = "out"
        outname = f"justifImpots{YEAR}.csv"
        journalName = f"journalComplet{YEAR}.csv"
        
        # Create output dir
        if not os.path.exists(outDir):
            try:
                os.mkdir(outDir)
            except Exception as E:
                print(f"Failed to create folder {outDir}")
                sys.exit(1)
                
        try:
            journal = open(os.path.join(outDir, journalName), "w")
        except Exception as E:
            print(f"Saving to CSV file {outname} failed")
            sys.exit(1)

        gains.process(journalFile=journal)
        
        try:
            with open(os.path.join(outDir, outname), "w") as outFile:
                print (f'"date","txid","gain","total"', file =outFile)
                _sum = 0.0
                for t,g,deposit in gains.wallet.gains:
                    if abs(g) + abs(deposit) < 1e-7:continue
                    if t.date.year != YEAR : continue
                    _sum += g
                    print (f"{t.date},{t.txid},{g:+7.2f},{_sum:+7.2f}", file =outFile)
        
        except Exception as E:
            printE(f"Saving to CSV file {outname} failed")
            sys.exit(1)
                
        journal.close()    
            
        print (f"Wallet content: ({gains.wallet.lastTransactionDate})")
        print ("| "+"\n| ".join(gains.wallet.asString()))
        
        for y in sorted(gains.wallet.gainsByYear):
            print(f"Year {y} : Gains = {gains.wallet.gainsByYear[y]:+5.0f} EUR")
    except CalcExcept as E: 
        printE (f"Error : {E}")
        if DO_DEBUG:raise E
        sys.exit(1)
    except BalanceError as E:
        printE (f"While processing transaction {E.txid}:")
        printE (f" -> Invalid balance in ledgers for {E.asset}: {E.msg}")
        try: fstDate = gains.wallet.firstTransactionDate
        except:fstDate=None
        printE (f"    This problem is generally due to an incomplete ledgers.zip exports from KRAKEN")
        printE (f"    You MUST export LEDGERS starting from the account opening, not only the current year")
        if fstDate != None:
            printE (f"  Note : Your LEDGERS entries start at {fstDate}")
        sys.exit(1)
    except Exception as E:
        printE (f"Error : {E}")
        if 1 : raise E
        sys.exit(1)
        
    print("Terminated successfully")