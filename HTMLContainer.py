#
# NOTICE:
# Portions of this software were produced for the U. S. Government
# under Contract No. FA8702-19-C-0001 and W56KGU-18-D-0004, and is subject to the Rights in Noncommercial Computer Software
# and Noncommercial Computer Software Documentation Clause DFARS 252.227-7014 (FEB 2014)
# (c) 2021 The MITRE Corporation
#
class HTMLContainer:

    timeline = """
<h1>Mouse Gestures on QTDC Timeline</h1>
<p/>
<h2>Data Time Window Manipulation:</h2>
<ul class="a">
    <li>Click LEFT button:  Set the position of the data time window</li>
    <li>Drag LEFT button:   Position of data time window follows mouse</li>
    <li>Drag RIGHT button:  Adjust time window duration.  The edge of the data time window closest to the mouse follows the mouse position.</li><br/>
    (Use caution when adjusting the Data Window time range to avoid making it too large as this can make QGIS unresponsive.)
</ul>
<p/>
<h2>Timeline View Zoom/Pan with Mouse and Meta-Keys:</h2>
<h2>Zoom:</h2>
<h3>Ctrl + Drag LEFT mouse button:</h3>
<ul class="a">
    <li>Drag to the RIGHT zooms the timeline view IN</li>
    <li>Drag to the LEFT zooms the timeline view OUT</li>
</ul>
<h3>Ctrl + Click RIGHT mouse button:</h3>
<ul class="a">
    <li> Reverts timeline zoom to previous level.</li>
</ul>
<h2>Pan:</h2>
<h3>SHIFT + Drag LEFT mouse button:</h3>
<ul class="a">
    <li>  The view position of timeline data follows the mouse position.</li>
</ul>
<p/>
<h1>Play control keyboard shortcuts</h1>
<h2> (with play button in focus):</h2>
<ul class="a">
    <li>A - set direction to reverse / step backward</li>
    <li>S - set direction to forward / step forward</li>
    <li>Z - toggle Play/Pause</li>
</ul>"""
