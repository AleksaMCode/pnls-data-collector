from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from stats.core.supabase._init_runtime import Base


class DailyImportsMac(Base):
    __tablename__ = "daily_imports_mac"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_mac_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class DailyImportsSsid(Base):
    __tablename__ = "daily_imports_ssid"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_ssid_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class DailyImportsProbes(Base):
    __tablename__ = "daily_imports_probes"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_probes_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class Device(Base):
    __tablename__ = "devices"

    device = Column(String, primary_key=True)
    location = Column(String, nullable=False)
    coordinates = Column(String, nullable=True)


class DeviceDailyImports(Base):
    __tablename__ = "device_daily_imports"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "date", name="uq_device_daily_imports_device_date"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device"), nullable=False, index=True)
    ssid = Column(BigInteger, nullable=False)
    mac = Column(BigInteger, nullable=False)
    probes = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)
