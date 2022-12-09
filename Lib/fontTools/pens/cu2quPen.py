# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, List, Optional, Tuple
from fontTools.cu2qu import curve_to_quadratic
from fontTools.pens.basePen import AbstractPen, decomposeSuperBezierSegment, PenPoint
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.pointPen import BasePointToSegmentPen, PointPenPathTuple
from fontTools.pens.pointPen import ReverseContourPointPen


class Cu2QuPen(AbstractPen):
    """ A filter pen to convert cubic bezier curves to quadratic b-splines
    using the FontTools SegmentPen protocol.

    Args:

        other_pen: another SegmentPen used to draw the transformed outline.
        max_err: maximum approximation error in font units. For optimal results,
            if you know the UPEM of the font, we recommend setting this to a
            value equal, or close to UPEM / 1000.
        reverse_direction: flip the contours' direction but keep starting point.
        stats: a dictionary counting the point numbers of quadratic segments.
        ignore_single_points: don't emit contours containing only a single point

    NOTE: The "ignore_single_points" argument is deprecated since v1.3.0,
    which dropped Robofab support. It's no longer needed to special-case
    UFO2-style anchors (aka "named points") when using ufoLib >= 2.0,
    as these are no longer drawn onto pens as single-point contours,
    but are handled separately as anchors.
    """

    def __init__(self, other_pen, max_err: float, reverse_direction=False,
                 stats=None, ignore_single_points=False) -> None:
        if reverse_direction:
            self.pen = ReverseContourPen(other_pen)
        else:
            self.pen = other_pen
        self.max_err = max_err
        self.stats = stats
        if ignore_single_points:
            import warnings
            warnings.warn("ignore_single_points is deprecated and "
                          "will be removed in future versions",
                          UserWarning, stacklevel=2)
        self.ignore_single_points = ignore_single_points
        self.start_pt: Optional[PenPoint] = None
        self.current_pt: Optional[PenPoint] = None

    def _check_contour_is_open(self) -> None:
        if self.current_pt is None:
            raise AssertionError("moveTo is required")

    def _check_contour_is_closed(self) -> None:
        if self.current_pt is not None:
            raise AssertionError("closePath or endPath is required")

    def _add_moveTo(self) -> None:
        if self.start_pt is not None:
            self.pen.moveTo(self.start_pt)
            self.start_pt = None

    def moveTo(self, pt: PenPoint) -> None:
        self._check_contour_is_closed()
        self.start_pt = self.current_pt = pt
        if not self.ignore_single_points:
            self._add_moveTo()

    def lineTo(self, pt: PenPoint) -> None:
        self._check_contour_is_open()
        self._add_moveTo()
        self.pen.lineTo(pt)
        self.current_pt = pt

    def qCurveTo(self, *points: Optional[PenPoint]) -> None:
        self._check_contour_is_open()
        n = len(points)
        if n == 1:
            pt0 = points[0]
            assert pt0 is not None
            self.lineTo(pt0)
        elif n > 1:
            self._add_moveTo()
            self.pen.qCurveTo(*points)
            self.current_pt = points[-1]
        else:
            raise AssertionError("illegal qcurve segment point count: %d" % n)

    def _curve_to_quadratic(self, pt1: PenPoint, pt2: PenPoint, pt3: PenPoint) -> None:
        curve = (self.current_pt, pt1, pt2, pt3)
        quadratic = curve_to_quadratic(curve, self.max_err)
        if self.stats is not None:
            n = str(len(quadratic) - 2)
            self.stats[n] = self.stats.get(n, 0) + 1
        self.qCurveTo(*quadratic[1:])

    def curveTo(self, *points: PenPoint) -> None:
        self._check_contour_is_open()
        n = len(points)
        if n == 3:
            # this is the most common case, so we special-case it
            self._curve_to_quadratic(*points)
        elif n > 3:
            for segment in decomposeSuperBezierSegment(list(points)):
                self._curve_to_quadratic(*segment)
        elif n == 2:
            self.qCurveTo(*points)
        elif n == 1:
            self.lineTo(points[0])
        else:
            raise AssertionError("illegal curve segment point count: %d" % n)

    def closePath(self) -> None:
        self._check_contour_is_open()
        if self.start_pt is None:
            # if 'start_pt' is _not_ None, we are ignoring single-point paths
            self.pen.closePath()
        self.current_pt = self.start_pt = None

    def endPath(self) -> None:
        self._check_contour_is_open()
        if self.start_pt is None:
            self.pen.endPath()
        self.current_pt = self.start_pt = None

    def addComponent(
        self,
        glyphName: str,
        transformation: Tuple[float, float, float, float, float, float],
    ) -> None:
        self._check_contour_is_closed()
        self.pen.addComponent(glyphName, transformation)


from typing_extensions import TypeAlias

FourTuplePoint: TypeAlias = Tuple[PenPoint, bool, Optional[str], Any]
FourTupleSegment: TypeAlias = Tuple[str, List[FourTuplePoint]]

class Cu2QuPointPen(BasePointToSegmentPen):
    """ A filter pen to convert cubic bezier curves to quadratic b-splines
    using the RoboFab PointPen protocol.

    Args:
        other_point_pen: another PointPen used to draw the transformed outline.
        max_err: maximum approximation error in font units. For optimal results,
            if you know the UPEM of the font, we recommend setting this to a
            value equal, or close to UPEM / 1000.
        reverse_direction: reverse the winding direction of all contours.
        stats: a dictionary counting the point numbers of quadratic segments.
    """

    def __init__(self, other_point_pen, max_err, reverse_direction=False,
                 stats=None) -> None:
        BasePointToSegmentPen.__init__(self)
        if reverse_direction:
            self.pen = ReverseContourPointPen(other_point_pen)
        else:
            self.pen = other_point_pen
        self.max_err = max_err
        self.stats = stats

    def _flushContour(self, segments: List[FourTupleSegment]) -> None:
        assert len(segments) >= 1
        closed = segments[0][0] != "move"
        new_segments: List[FourTupleSegment] = []
        prev_points = segments[-1][1]
        prev_on_curve = prev_points[-1][0]
        for segment_type, points in segments:
            if segment_type == 'curve':
                for sub_points in self._split_super_bezier_segments(points):
                    on_curve, smooth, name, kwargs = sub_points[-1]
                    bcp1, bcp2 = sub_points[0][0], sub_points[1][0]
                    cubic = [prev_on_curve, bcp1, bcp2, on_curve]
                    quad = curve_to_quadratic(cubic, self.max_err)
                    if self.stats is not None:
                        n = str(len(quad) - 2)
                        self.stats[n] = self.stats.get(n, 0) + 1
                    new_points: List[FourTuplePoint] = [
                        (pt, False, None, {}) for pt in quad[1:-1]
                    ]
                    new_points.append((on_curve, smooth, name, kwargs))
                    new_segments.append(("qcurve", new_points))
                    prev_on_curve = sub_points[-1][0]
            else:
                new_segments.append((segment_type, points))
                prev_on_curve = points[-1][0]
        if closed:
            # the BasePointToSegmentPen.endPath method that calls _flushContour
            # rotates the point list of closed contours so that they end with
            # the first on-curve point. We restore the original starting point.
            new_segments = new_segments[-1:] + new_segments[:-1]
        self._drawPoints(new_segments)

    def _split_super_bezier_segments(self, points: List[FourTuplePoint]) -> List[List[FourTuplePoint]]:
        sub_segments: List[List[FourTuplePoint]] = []
        # n is the number of control points
        n = len(points) - 1
        if n == 2:
            # a simple bezier curve segment
            sub_segments.append(points)
        elif n > 2:
            # a "super" bezier; decompose it
            on_curve, smooth, name, kwargs = points[-1]
            num_sub_segments = n - 1
            for i, sub_points in enumerate(decomposeSuperBezierSegment([
                    pt for pt, _, _, _ in points])):
                new_segment: List[FourTuplePoint] = []
                for point in sub_points[:-1]:
                    new_segment.append((point, False, None, {}))
                if i == (num_sub_segments - 1):
                    # the last on-curve keeps its original attributes
                    new_segment.append((on_curve, smooth, name, kwargs))
                else:
                    # on-curves of sub-segments are always "smooth"
                    new_segment.append((sub_points[-1], True, None, {}))
                sub_segments.append(new_segment)
        else:
            raise AssertionError(
                "expected 2 control points, found: %d" % n)
        return sub_segments

    def _drawPoints(self, segments: List[FourTupleSegment]) -> None:
        pen = self.pen
        pen.beginPath()
        last_offcurves = []
        for i, (segment_type, points) in enumerate(segments):
            if segment_type in ("move", "line"):
                assert len(points) == 1, (
                    "illegal line segment point count: %d" % len(points))
                pt, smooth, name, kwargs = points[0]
                pen.addPoint(pt, segment_type, smooth, name, **kwargs)
            elif segment_type == "qcurve":
                assert len(points) >= 2, (
                    "illegal qcurve segment point count: %d" % len(points))
                offcurves = points[:-1]
                if offcurves:
                    if i == 0:
                        # any off-curve points preceding the first on-curve
                        # will be appended at the end of the contour
                        last_offcurves = offcurves
                    else:
                        for (pt, smooth, name, kwargs) in offcurves:
                            pen.addPoint(pt, None, smooth, name, **kwargs)
                pt, smooth, name, kwargs = points[-1]
                if pt is None:
                    # special quadratic contour with no on-curve points:
                    # we need to skip the "None" point. See also the Pen
                    # protocol's qCurveTo() method and fontTools.pens.basePen
                    pass
                else:
                    pen.addPoint(pt, segment_type, smooth, name, **kwargs)
            else:
                # 'curve' segments must have been converted to 'qcurve' by now
                raise AssertionError(
                    "unexpected segment type: %r" % segment_type)
        for (pt, smooth, name, kwargs) in last_offcurves:
            pen.addPoint(pt, None, smooth, name, **kwargs)
        pen.endPath()

    def addComponent(
        self,
        glyphName: str,
        transformation: Tuple[float, float, float, float, float, float],
        identifier: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        assert self.currentPath is None
        self.pen.addComponent(glyphName, transformation, identifier, **kwargs)
