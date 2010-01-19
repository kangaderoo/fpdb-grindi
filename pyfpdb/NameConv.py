#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Copyright 2010, Gerko de Roo
#    
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#    
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#    
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
########################################################################

import sys
import re


re_code_hex = re.compile ("""
   (?P<HEX>\S{2})""",
   re.MULTILINE|re.VERBOSE)
       
def tohex(s):
    _name = ""
    for i in range(len(s)):
        _name = "%s%x" % (_name, int(ord(s[i])))
    return _name

def fromhex(s):
    m = re_code_hex.finditer(s)
    _name = ""
    for i in m:
        _name = "%s%s" % (_name, chr(int(i.group('HEX'),16)))
    return _name

temp1 = tohex('Ãfonya76')
temp2 = fromhex('c38166676e79613736')

temp1 = ""