from counterpoint.chat import Chat


class Pipeline:
    """Pipeline represents a workflow that can be run"""


    async def run(self) -> Chat:
        ...

    async def run_many(self, n: int):
        ...

    async def run_batch(self, batch: list[dict]):
        ...