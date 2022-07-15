#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2022 The MITRE Corporation
#
#
# This class is a container for arguments for drawing decorator objects (i.e., labels, line endpoints)
#
class decoratorArgs:
    def __init__(self):
        self.xoffset = 10
        self.yoffset = 10
        self.fontsize = 10
        self.drawendpoints = False

    def loadFromList(self, l):
        if len(l) == 4:
            self.xoffset = l[0]
            self.yoffset = l[1]
            self.fontsize = l[2]
            self.drawendpoints = l[3]
