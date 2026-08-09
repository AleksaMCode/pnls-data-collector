from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    text,
)

from ssid_geo_mapper.core.orm._init_runtime import Base


class SSIDGeo(Base):
    __tablename__ = "ssid_geo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(Integer, ForeignKey("ssid.id", ondelete="CASCADE"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    country = Column(
        Integer, ForeignKey("country.id", ondelete="SET NULL"), nullable=True
    )
    created_date = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))


class SSIDGeoReduced(Base):
    __tablename__ = "ssid_geo_reduced"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(Integer, ForeignKey("ssid.id", ondelete="CASCADE"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    country = Column(
        Integer, ForeignKey("country.id", ondelete="SET NULL"), nullable=True
    )
    created_date = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))


class SSID(Base):
    __tablename__ = "ssid"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String(255), unique=True, nullable=False)

    mapped = Column(Boolean, nullable=False, default=False)
    has_geo = Column(Boolean, nullable=False, default=False)


class Country(Base):
    __tablename__ = "country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    alpha2 = Column(CHAR(2), unique=True, nullable=False)
    alpha3 = Column(CHAR(3), unique=True, nullable=False)
    country_code = Column(CHAR(3), unique=True, nullable=False)
    region = Column(String, nullable=True)
    sub_region = Column(String, nullable=True)
    intermediate_region = Column(String, nullable=True)
    region_code = Column(Integer, nullable=True)
    sub_region_code = Column(Integer, nullable=True)
    intermediate_region_code = Column(Integer, nullable=True)
