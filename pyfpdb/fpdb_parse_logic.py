#!/usr/bin/python

#Copyright 2008 Steffen Jobbagy-Felso
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as published by
#the Free Software Foundation, version 3 of the License.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU Affero General Public License
#along with this program. If not, see <http://www.gnu.org/licenses/>.
#In the "official" distribution you can find the license in
#agpl-3.0.txt in the docs folder of the package.

#parses an in-memory fpdb hand history and calls db routine to store it

import sys
from time import time, strftime
from Exceptions import *

import fpdb_simple
import Database

def mainParser(settings, siteID, category, hand, config, db = None, writeq = None):
    """ mainParser for Holdem Hands """
    t0 = time()
    backend = settings['db-backend']
    # Ideally db connection is passed in, if not use sql list if passed in,
    # otherwise start from scratch
    if db is None:
        db = Database.Database(c = config, sql = None)
    category = fpdb_simple.recogniseCategory(hand[0])

    base = "hold" if (category == "holdem" or category == "omahahi" or
                      category == "omahahilo") else "stud"

    #part 0: create the empty arrays
    # lineTypes valid values: header, name, cards, action, win, rake, ignore
    # lineStreets valid values: predeal, preflop, flop, turn, river
    lineTypes   = [] 
    lineStreets = [] 
    cardValues = []
    cardSuits = []
    boardValues = []
    boardSuits = []
    antes = []
    allIns = []
    actionAmounts = []
    actionNos = []
    actionTypes = []
    actionTypeByNo = []
    seatLines = []
    winnings = []
    rakes = []

    #part 1: read hand no and check for duplicate
    siteHandNo      = fpdb_simple.parseSiteHandNo(hand[0])
    handStartTime   = fpdb_simple.parseHandStartTime(hand[0])    
    isTourney       = fpdb_simple.isTourney(hand[0])
    
    smallBlindLine  = None
    for i, line in enumerate(hand):
        if 'posts small blind' in line or 'posts the small blind' in line:
            if line[-2:] == "$0": continue
            smallBlindLine = i
            break
    else:
        smallBlindLine = 0
        # If we did not find a small blind line, what happens?
        # if we leave it at None, it errors two lines down.

    gametypeID = fpdb_simple.recogniseGametypeID(backend, db, db.get_cursor(),
                                                 hand[0], hand[smallBlindLine],
                                                 siteID, category, isTourney)
    if isTourney:
        siteTourneyNo   = fpdb_simple.parseTourneyNo(hand[0])
        buyin           = fpdb_simple.parseBuyin(hand[0])
        fee             = fpdb_simple.parseFee(hand[0])
        entries         = -1 #todo: parse this
        prizepool       = -1 #todo: parse this
        knockout        = False
        tourneyStartTime= handStartTime #todo: read tourney start time
        rebuyOrAddon    = fpdb_simple.isRebuyOrAddon(hand[0])

        # The tourney site id has to be searched because it may already be in
        # db with a TourneyTypeId which is different from the one automatically
        # calculated (Summary import first) 
        tourneyTypeId   = fpdb_simple.recogniseTourneyTypeId(db, siteID,
                                                             siteTourneyNo,
                                                             buyin, fee,
                                                             knockout,
                                                             rebuyOrAddon)
    else:
        siteTourneyNo   = -1
        buyin           = -1
        fee             = -1
        entries         = -1
        prizepool       = -1
        knockout        = 0
        tourneyStartTime= None
        rebuyOrAddon    = -1

        tourneyTypeId   = 1
    fpdb_simple.isAlreadyInDB(db, gametypeID, siteHandNo)
    
    hand = fpdb_simple.filterCrap(hand, isTourney)
    
    #part 2: classify lines by type (e.g. cards, action, win, sectionchange) and street
    fpdb_simple.classifyLines(hand, category, lineTypes, lineStreets)
        
    #part 3: read basic player info    
    #3a read player names, startcashes
    for i, line in enumerate(hand):
        if lineTypes[i] == "name":
            seatLines.append(line)

    names       = fpdb_simple.parseNames(seatLines)
    playerIDs   = db.recognisePlayerIDs(names, siteID)  # inserts players as needed
    tmp         = fpdb_simple.parseCashesAndSeatNos(seatLines)
    startCashes = tmp['startCashes']
    seatNos     = tmp['seatNos']
    
    fpdb_simple.createArrays(category, len(names), cardValues, cardSuits, antes,
                             winnings, rakes, actionTypes, allIns,
                             actionAmounts, actionNos, actionTypeByNo)
    
    #3b read positions
    if base == "hold":
        positions = fpdb_simple.parsePositions(hand, names)
    
    #part 4: take appropriate action for each line based on linetype
    for i, line in enumerate(hand):
        if lineTypes[i] == "cards":
            fpdb_simple.parseCardLine(category, lineStreets[i], line, names,
                                      cardValues, cardSuits, boardValues,
                                      boardSuits)
            #if category=="studhilo":
            #    print "hand[i]:", hand[i]
            #    print "cardValues:", cardValues
            #    print "cardSuits:", cardSuits
        elif lineTypes[i] == "action":
            fpdb_simple.parseActionLine(base, isTourney, line, lineStreets[i],
                                        playerIDs, names, actionTypes, allIns,
                                        actionAmounts, actionNos, actionTypeByNo)
        elif lineTypes[i] == "win":
            fpdb_simple.parseWinLine(line, names, winnings, isTourney)
        elif lineTypes[i] == "rake":
            totalRake = 0 if isTourney else fpdb_simple.parseRake(line)
            fpdb_simple.splitRake(winnings, rakes, totalRake)
        elif (lineTypes[i] == "header" or lineTypes[i] == "rake" or
              lineTypes[i] == "name" or lineTypes[i] == "ignore"):
            pass
        elif lineTypes[i] == "ante":
            fpdb_simple.parseAnteLine(line, isTourney, names, antes)
        elif lineTypes[i] == "table":
            tableResult=fpdb_simple.parseTableLine(base, line)
        else:
            raise FpdbError("unrecognised lineType:" + lineTypes[i])
            
    maxSeats    = tableResult['maxSeats']
    tableName   = tableResult['tableName']
    #print "before part5, antes:", antes
    
    #part 5: final preparations, then call Database.* with
    #         the arrays as they are - that file will fill them.
    fpdb_simple.convertCardValues(cardValues)
    if base == "hold":
        fpdb_simple.convertCardValuesBoard(boardValues)
        fpdb_simple.convertBlindBet(actionTypes, actionAmounts)
        fpdb_simple.checkPositions(positions)
        
    c = db.get_cursor()
    c.execute("SELECT limitType FROM Gametypes WHERE id=%s" % (db.sql.query['placeholder'],), (gametypeID, ))
    limit_type = c.fetchone()[0]
    fpdb_simple.convert3B4B(category, limit_type, actionTypes, actionAmounts)
    
    totalWinnings = sum(winnings)
    
    # if hold'em, use positions and not antes, if stud do not use positions, use antes
    # this is used for handsplayers inserts, so still needed even if hudcache update is being skipped
    if base == "hold":
        hudImportData = fpdb_simple.generateHudCacheData(playerIDs, base,
                                                         category, actionTypes,
                                                         allIns, actionTypeByNo,
                                                         winnings,
                                                         totalWinnings,
                                                         positions, actionTypes,
                                                         actionAmounts, None)
    else:
        hudImportData = fpdb_simple.generateHudCacheData(playerIDs, base,
                                                         category, actionTypes,
                                                         allIns, actionTypeByNo,
                                                         winnings,
                                                         totalWinnings, None,
                                                         actionTypes,
                                                         actionAmounts, antes)

    try:
        db.commit()  # need to commit new players as different db connection used 
                         # for other writes. maybe this will change maybe not ...
    except: # TODO: this really needs to be narrowed down
        print "parse: error during commit: " + str(sys.exc_value)

#    HERE's an ugly kludge to keep from failing when positions is undef
#    We'll fix this by getting rid of the legacy importer.  REB
    try:
        if positions:
            pass
    except NameError:
        positions = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    # save data structures in a HandToWrite instance and then insert into database: 
    htw = Database.HandToWrite()
    htw.set_all( config, settings, base, category, siteTourneyNo, buyin
               , fee, knockout, entries, prizepool, tourneyStartTime
               , isTourney, tourneyTypeId, siteID, siteHandNo
               , gametypeID, handStartTime, names, playerIDs, startCashes
               , positions, antes, cardValues, cardSuits, boardValues, boardSuits
               , winnings, rakes, actionTypes, allIns, actionAmounts
               , actionNos, hudImportData, maxSeats, tableName, seatNos)

    # save hand in db via direct call or via q if in a thread
    if writeq is None:
        result = db.store_the_hand(htw)
    else:
        writeq.put(htw)
        result = -999  # meaning unknown

    t9 = time()
    #print "parse and save=(%4.3f)" % (t9-t0)
    return result
#end def mainParser

