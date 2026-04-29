from sqlalchemy.types import UserDefinedType

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ModuleNotFoundError:

    class PgVector(UserDefinedType):
        cache_ok = True

        def __init__(self, dim: int) -> None:
            self.dim = dim

        def get_col_spec(self, **kw) -> str:
            return f"VECTOR({self.dim})"


Vector = PgVector
