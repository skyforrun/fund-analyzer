from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "fund_analyzer"
    user: str = "postgres"
    password: str = ""

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class FundPoolConfig:
    min_inception_years: int = 2
    min_size_billion: float = 1
    exclude_types: list[str] = field(default_factory=lambda: ["货币型", "纯债型"])


@dataclass
class DataConfig:
    sync_interval_seconds: float = 0.5
    retry_count: int = 3
    fund_pool: FundPoolConfig = field(default_factory=FundPoolConfig)


@dataclass
class PortfolioConfig:
    core_ratio: int = 30
    satellite_ratio: int = 70


@dataclass
class SignalThresholds:
    buy: float = 80
    sell: float = 60


@dataclass
class StrategyConfig:
    dynamic_weights: bool = False
    signal_thresholds: SignalThresholds = field(default_factory=SignalThresholds)
    core: dict[str, float] = field(default_factory=lambda: {"factor": 70, "global_alloc": 30})
    satellite: dict[str, float] = field(default_factory=lambda: {"momentum": 40, "rotation": 35, "global_alloc": 25})


@dataclass
class BacktestConfig:
    default_start: str = "2020-01-01"
    initial_capital: float = 100000
    core_top_n: int = 3
    satellite_top_n: int = 7
    core_rebalance_freq: str = "quarterly"
    satellite_rebalance_freq: str = "monthly"
    buy_fee_rate: float = 0.0015
    sell_fee_rate: float = 0.005


@dataclass
class SmartDipConfig:
    low_pe_percentile: float = 30
    high_pe_percentile: float = 70
    low_multiplier: float = 1.5
    high_multiplier: float = 0.5


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/fund_analyzer.log"


@dataclass
class Settings:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    smart_dip: SmartDipConfig = field(default_factory=SmartDipConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _dict_to_dataclass(cls, data: dict):
    if data is None:
        return cls()
    kwargs = {}
    for key, value in data.items():
        if key in cls.__dataclass_fields__:
            field_meta = cls.__dataclass_fields__[key]
            field_type = field_meta.type
            if isinstance(field_type, str):
                field_type = eval(field_type)
            if isinstance(value, dict) and hasattr(field_type, "__dataclass_fields__"):
                kwargs[key] = _dict_to_dataclass(field_type, value)
            else:
                kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str) -> Settings:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    settings = _dict_to_dataclass(Settings, raw)

    env_password = os.environ.get("FUND_DB_PASSWORD")
    if env_password and not settings.database.password:
        settings.database.password = env_password

    return settings
