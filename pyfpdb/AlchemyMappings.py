# -*- coding: utf-8 -*-
"""@package AlchemyMappings
This package contains all classes to be mapped and mappers themselves
"""

import logging
from decimal import Decimal
from sqlalchemy.orm import mapper, relation
from sqlalchemy.sql import select


from AlchemyTables import *
from AlchemyFacilities import get_or_create, MappedBase
from DerivedStats import DerivedStats


class Player(MappedBase):
    """Class reflecting Players db table"""

    @staticmethod
    def get_or_create(session, siteId, name):
        return get_or_create(Player, session, siteId=siteId, name=name)[0]

    def __str__(self):
        return '<Player "%s" on %s>' % (self.name, self.site and self.site.name)


class Gametype(MappedBase):
    """Class reflecting Gametypes db table"""

    @staticmethod
    def get_or_create(session, siteId, gametype):
        map = zip(
            ['type', 'base', 'category', 'limitType', 'smallBlind', 'bigBlind', 'smallBet', 'bigBet'],
            ['type', 'base', 'category', 'limitType', 'sb', 'bb', 'dummy', 'dummy', ])
        gametype = dict([(new, gametype.get(old)) for new, old in map  ])

        hilo = "h"
        if gametype['category'] in ('studhilo', 'omahahilo'):
            hilo = "s"
        elif gametype['category'] in ('razz','27_3draw','badugi'):
            hilo = "l"
        gametype['hiLo'] = hilo

        for f in ['smallBlind', 'bigBlind', 'smallBet', 'bigBet']:
            if gametype[f] is None: 
                gametype[f] = 0
            gametype[f] = int(Decimal(gametype[f])*100)

        gametype['siteId'] = siteId
        return get_or_create(Gametype, session, **gametype)[0]


class HandAction(object):
    """Class reflecting HandsActions db table"""
    def initFromImportedHand(self, action_tuple, actionNo=None, street=None, handPlayer=None):
        if actionNo is not None: self.actionNo = actionNo
        if handPlayer is not None: self.handPlayer = handPlayer
        if street is not None: self.street = street
        #import pdb; pdb.set_trace()
        action, extra = action_tuple[1], action_tuple[2:] # we don't need player name 
        self.action = action
        # FIXME: add support for 'discards'. I have no idea \
        # how to put discarded cards here \\grindi
            # The schema for draw games hasn't been decided - ignoring it is correct \\ Carl G
        if action in ('folds', 'checks', 'stands pat'):
            pass
        elif action in ('bets', 'calls', 'bringin'):
            self.amount, self.allIn = extra
        elif action == 'raises':
            Rb, Rt, C, self.allIn = extra
            self.amount = Rt 
        elif action == 'posts':
            blindtype, self.amount, self.allIn = extra
            self.action = '%s %s' % (action, blindtype)
        elif action == 'ante':
             self.amount, self.allIn = extra


class HandInternal(DerivedStats):
    """Class reflecting Hands db table"""

    def parseImportedHandStep1(self, hand):
        """Extracts values to insert into from hand returned by HHC. No db is needed he"""
        hand.players = hand.getAlivePlayers() 

        # also save some data for step2. Those fields aren't in Hands table
        self.siteId = hand.siteId 
        self.gametype_dict = hand.gametype 

        self.attachHandPlayers(hand)
        #self.attachActions(hand) #FIXME: write actions and uncomment line below

        self.assembleHands(hand)
        self.assembleHandsPlayers(hand)

    def parseImportedHandStep2(self, session):
        """Fetching ids for gametypes and players"""
        self.gametypeId = Gametype.get_or_create(session, self.siteId, self.gametype_dict).id
        for hp in self.handPlayers:
            hp.playerId = Player.get_or_create(session, self.siteId, hp.name).id

    def getPlayerByName(self, name):
        for hp in self.handPlayers:
            pname = (hp.player and hp.player.name) or hp.name
            if pname == name:
                return hp

    def attachHandPlayers(self, hand):
        """Fills HandInternal.handPlayers list"""
        self.handplayers_by_name = {}
        for seat, name, chips in hand.players:
            p = HandPlayer(hand = self, imported_hand=hand, seatNo=seat, 
                           name=name, startCash=chips)         
            self.handplayers_by_name[name] = p
        
    def attachActions(self, hand):
        """Fills HandPlayers.actions list for each attached player"""
        for street, actions in hand.actions.iteritems():
            for i, action in enumerate(actions):
                p = self.handplayers_by_name[action[0]]
                a = HandAction()
                a.initFromImportedHand(action, actionNo=i, street=street, handPlayer=p)
                p.actions.append(a)

    def isDuplicate(self, session):
        """Checks if current hand already exists in db
        
        siteHandNo ans gameTypeId have to be setted
        """
        return session.query(HandInternal).filter_by(
                siteHandNo=self.siteHandNo, gametypeId=self.gametypeId).count()!=0

    def __str__(self):
        s = list()
        for i in self._sa_class_manager.mapper.c:
            s.append('%25s     %s' % (i, getattr(self, i.name)))

        s+=['', '']
        for i,p in enumerate(self.handPlayers):
            s.append('%d. %s' % (i, p.player.name or '???'))
        return '\n'.join(s)


class HandPlayer(MappedBase):
    """Class reflecting HandsPlayers db table"""
    def __init__(self, **kwargs):
        if 'imported_hand' in kwargs and 'seatNo' in kwargs:
            imported_hand = kwargs.pop('imported_hand')
            self.position = self.getPosition(imported_hand, kwargs['seatNo'])
        super(HandPlayer, self).__init__(**kwargs)

    @staticmethod
    def getPosition(hand, seat):
        """Returns position value like 'B', 'S', 0, 1, ...

        >>> class A(object): pass
        ... 
        >>> A.maxseats = 6
        >>> A.buttonpos = 2
        >>> A.gametype = {'base': 'hold'}
        >>> HandInternal.getPosition(A, 2)
        '0'
        >>> HandInternal.getPosition(A, 1)
        'B'
        >>> HandInternal.getPosition(A, 6)
        'S'
        """
        from itertools import chain
        if hand.gametype['base'] == 'stud':
            # FIXME: i've never played stud so plz check & del comment \\grindi
            bringin = None
            for action in chain(*[self.actions[street] for street in hand.allStreets]):
                if action[1]=='bringin':
                    bringin = action[0]
                    break
            if bringin is None:
                raise Exception, "Cannot find bringin"
            # name -> seat
            bringin = int(filter(lambda p: p[1]==bringin, bringin)[0])
            seat = (int(seat) - int(bringin))%int(hand.maxseats)
            return str(seat)
        else:
            seat = (int(seat) - int(hand.buttonpos) + 2)%int(hand.maxseats) - 2
            if seat == -2:
                return 'S'
            elif seat == -1:
                return 'B'
            else:
                return str(seat)


class Site(object):
    """Class reflecting Players db table"""
    INITIAL_DATA = [
            (1 , 'Full Tilt Poker','USD'),
            (2 , 'PokerStars',     'USD'),
            (3 , 'Everleaf',       'USD'),
            (4 , 'Win2day',        'USD'),
            (5 , 'OnGame',         'USD'),
            (6 , 'UltimateBet',    'USD'),
            (7 , 'Betfair',        'USD'),
            (8 , 'Absolute',       'USD'),
            (9 , 'PartyPoker',     'USD'),
            (10, 'Partouche',      'EUR'),
        ]
    INITIAL_DATA_KEYS = ('id', 'name', 'currency')

    INITIAL_DATA_DICTS = [ dict(zip(INITIAL_DATA_KEYS, datum)) for datum in INITIAL_DATA ] 

    @classmethod
    def insert_initial(cls, connection):
        connection.execute(sites_table.insert(), cls.INITIAL_DATA_DICTS)


class Version(object):
    """Provides read/write access for version var"""
    CURRENT_VERSION = 118 # db version for current release

    conn = None 
    ver  = None
    def __init__(self, connection=None):
        if self.__class__.conn is None:
            self.__class__.conn = connection

    @classmethod
    def is_wrong(cls):
        return cls.get() != cls.CURRENT_VERSION

    @classmethod
    def get(cls):
        if cls.ver is None:
           cls.ver = cls.conn.execute(select(['version'], settings_table)).fetchone()[0]
        return cls.ver

    @classmethod
    def set(cls, value):
        if cls.ver is None:
            cls.conn.execute(settings_table.insert(), version=value)
        else:
            cls.conn.execute(settings_table.update().values(version=value))
        cls.ver = None
    


mapper (Gametype, gametypes_table, properties={
    'hands': relation(HandInternal, backref='gametype'),
})
mapper (Player, players_table, properties={
    'playerHands': relation(HandPlayer, backref='player'),
})
mapper (Site, sites_table, properties={
    'players': relation(Player, backref = 'site'),
    'gametypes': relation(Gametype, backref = 'site'),
})
mapper (HandAction, hands_actions_table, properties={})
mapper (HandInternal, hands_table, properties={
    'handPlayers': relation(HandPlayer, backref='hand'),
})
mapper (HandPlayer, hands_players_table, properties={
    'actions': relation(HandAction, backref='handPlayer'),
})
