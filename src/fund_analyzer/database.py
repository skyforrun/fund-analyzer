from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from fund_analyzer.config import Settings


def create_db_engine(settings: Settings):
    return create_engine(settings.database.url, echo=False)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_db_engine(settings)
    return sessionmaker(bind=engine)
