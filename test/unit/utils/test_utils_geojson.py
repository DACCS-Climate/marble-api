from marble_api.utils.geojson import bbox_from_coordinates


class TestBboxFromCoordinates:
    def test_2d_point(self):
        assert bbox_from_coordinates([1, 2]) == [1, 1, 2, 2]

    def test_3d_point(self):
        assert bbox_from_coordinates([1, 2, 3]) == [1, 1, 2, 2, 3, 3]

    def test_2d_line(self):
        assert bbox_from_coordinates([[1, 2], [-1, -3]]) == [-1, 1, -3, 2]

    def test_3d_line(self):
        assert bbox_from_coordinates([[1, 2, 4], [-1, -3, 33]]) == [-1, 1, -3, 2, 4, 33]

    def test_mixed_d_line(self):
        assert bbox_from_coordinates([[1, 2], [-1, -3, 33]]) == [-1, 1, -3, 2, 0, 33]

    def test_deeply_nested(self):
        assert bbox_from_coordinates([[[[1, 2], [-1, -3, 33]]]]) == [-1, 1, -3, 2, 0, 33]

    def test_different_nested(self):
        assert bbox_from_coordinates([[1, 2], [[[-1, -3, 33]]]]) == [-1, 1, -3, 2, 0, 33]
