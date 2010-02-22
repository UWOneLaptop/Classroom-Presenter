# ink.py
#
# B. Mayton <bmayton@cs.washington.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import random
import logging

class Path:

    def __init__(self, inkstr=None):

        self.__logger = logging.getLogger('Path')
        self.__logger.setLevel(logging.DEBUG)

        self.points=[]
        self.color = (0,0,1.0)
        self.pen = 4
        self.uid = random.randint(0, 2147483647)
        if inkstr:
            try:
                i=0
                parts = inkstr.split('#')
                if len(parts) > 1:
                    params = parts[i].split(';')
                    self.uid = int(params[0])
                    colorparts = params[1].split(',')
                    self.color = (float(colorparts[0]),float(colorparts[1]),float(colorparts[2]))
                    self.pen = float(params[2])
                    i = i + 1
                    pathstr = parts[i]
                    pointstrs = pathstr.split(';')
                    for pointstr in pointstrs:
                        pparts = pointstr.split(',')
                        if len(pparts) == 2:
                            self.add((int(pparts[0]), int(pparts[1])))
            except Exception, e:
                self.__logger.debug('Could not unserialize ink string (old ink?)')
                
    def add(self, point):
        self.points.append(point)
        
    def __str__(self):
        s = str(self.uid) + ";"
        s = s +  str(self.color[0]) + "," + str(self.color[1]) + "," + str(self.color[2]) + ";"
        s = s + str(self.pen) + "#"
        for p in self.points:
            s = s + str(int(p[0])) + "," + str(int(p[1])) + ";"
        return s
