import os
import re
import codecs
import Options
import HandHistoryConverter

(options, argv) = Options.fpdb_options()

filter = options.hhc

filter_name = filter.replace("ToFpdb", "")

mod = __import__(filter)
obj = getattr(mod, filter_name, None)

hhc = obj(autostart=False)

if os.path.exists(options.infile):
    in_fh = codecs.open(options.infile, 'r', "utf8")
    filecontents = in_fh.read()
    in_fh.close()
else:
    print "Could not find file %s" % options.infile
    exit(1)

m = hhc.re_PlayerInfo.finditer(filecontents)

players = []
for a in m:
    players = players + [a.group('PNAME')]

uniq = set(players)

for i, name in enumerate(uniq, 1):
    filecontents = filecontents.replace(name, 'Player%d' %i)

print filecontents
