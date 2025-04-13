from line_works.client import LineWorks


class LineWorksFixture:
    def __init__(self):
        pass

    def init(self, works: LineWorks):
        self.works = works

    def __call__(self):
        return self.works


line_works_depends = LineWorksFixture()
