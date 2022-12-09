from typing import Any, List, Optional, Sequence, Tuple, Union
from fontTools.misc.transform import Transform
from fontTools.pens.basePen import PenPoint
from fontTools.pens.filterPen import FilterPen, FilterPointPen


__all__ = ["TransformPen", "TransformPointPen"]


class TransformPen(FilterPen):

	"""Pen that transforms all coordinates using a Affine transformation,
	and passes them to another pen.
	"""

	def __init__(self, outPen, transformation: Union[Transform, Tuple[float, float, float, float, float, float]]) -> None:
		"""The 'outPen' argument is another pen object. It will receive the
		transformed coordinates. The 'transformation' argument can either
		be a six-tuple, or a fontTools.misc.transform.Transform object.
		"""
		super(TransformPen, self).__init__(outPen)
		if isinstance(transformation, Transform):
			transform = transformation
		else:
			transform = Transform(*transformation)
		self._transformation = transform
		self._transformPoint = transform.transformPoint
		self._stack: List[Any] = []

	def moveTo(self, pt: PenPoint) -> None:
		self._outPen.moveTo(self._transformPoint(pt))

	def lineTo(self, pt: PenPoint) -> None:
		self._outPen.lineTo(self._transformPoint(pt))

	def curveTo(self, *points: PenPoint) -> None:
		self._outPen.curveTo(*self._transformPoints(list(points)))

	def qCurveTo(self, *points: Optional[PenPoint]) -> None:
		pt = points[-1]
		if pt is None:
			tpoints = self._transformPoints(points[:-1]) + [None]
		else:
			tpoints = self._transformPoints(points)
		self._outPen.qCurveTo(*tpoints)

	def _transformPoints(self, points: Sequence[PenPoint]) -> List[PenPoint]:
		transformPoint = self._transformPoint
		return [transformPoint(pt) for pt in points]

	def closePath(self) -> None:
		self._outPen.closePath()

	def endPath(self) -> None:
		self._outPen.endPath()

	def addComponent(
		self,
		glyphName: str,
		transformation: Tuple[float, float, float, float, float, float],
	) -> None:
		transformation = self._transformation.transform(transformation)
		self._outPen.addComponent(glyphName, transformation)


class TransformPointPen(FilterPointPen):
	"""PointPen that transforms all coordinates using a Affine transformation,
	and passes them to another PointPen.

	>>> from fontTools.pens.recordingPen import RecordingPointPen
	>>> rec = RecordingPointPen()
	>>> pen = TransformPointPen(rec, (2, 0, 0, 2, -10, 5))
	>>> v = iter(rec.value)
	>>> pen.beginPath(identifier="contour-0")
	>>> next(v)
	('beginPath', (), {'identifier': 'contour-0'})
	>>> pen.addPoint((100, 100), "line")
	>>> next(v)
	('addPoint', ((190, 205), 'line', False, None), {})
	>>> pen.endPath()
	>>> next(v)
	('endPath', (), {})
	>>> pen.addComponent("a", (1, 0, 0, 1, -10, 5), identifier="component-0")
	>>> next(v)
	('addComponent', ('a', <Transform [2 0 0 2 -30 15]>), {'identifier': 'component-0'})
	"""

	def __init__(self, outPointPen, transformation):
		"""The 'outPointPen' argument is another point pen object.
		It will receive the transformed coordinates.
		The 'transformation' argument can either be a six-tuple, or a
		fontTools.misc.transform.Transform object.
		"""
		super().__init__(outPointPen)
		if not hasattr(transformation, "transformPoint"):
			from fontTools.misc.transform import Transform
			transformation = Transform(*transformation)
		self._transformation = transformation
		self._transformPoint = transformation.transformPoint

	def addPoint(
		self,
		pt: PenPoint,
		segmentType: Optional[str] = None,
		smooth: bool = False,
		name: Optional[str] = None,
		identifier: Optional[str] = None,
		**kwargs: Any
	) -> None:
		self._outPen.addPoint(
			self._transformPoint(pt), segmentType, smooth, name, identifier, **kwargs
		)

	def addComponent(
		self,
		glyphName: str,
		transformation: Tuple[float, float, float, float, float, float],
		identifier: Optional[str] = None,
		**kwargs: Any
	) -> None:
		transformation = self._transformation.transform(transformation)
		self._outPen.addComponent(glyphName, transformation, identifier, **kwargs)


if __name__ == "__main__":
	from fontTools.pens.basePen import _TestPen
	pen = TransformPen(_TestPen(None), (2, 0, 0.5, 2, -10, 0))
	pen.moveTo((0, 0))
	pen.lineTo((0, 100))
	pen.curveTo((50, 75), (60, 50), (50, 25), (0, 0))
	pen.closePath()
