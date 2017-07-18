drop table if exists devices;
create table devices (
  id integer primary key autoincrement,
  serial_number text not null,
  asset_tag text,
  device_name text,
  dt_sub_to_jss DATETIME
);

drop table if exists settings;
create table settings (
  id integer primary key autoincrement,
  setting_name text,
  setting_value text
);
