#!/bin/sh
set -eu

: "${POSTGRES_ADMIN_DSN:?POSTGRES_ADMIN_DSN is required}"
: "${POSTGRES_SOURCE_DSN:?POSTGRES_SOURCE_DSN is required}"
: "${POSTGRES_RESTORE_DSN:?POSTGRES_RESTORE_DSN is required}"
: "${POSTGRES_RESTORE_DB:?POSTGRES_RESTORE_DB is required}"
: "${POSTGRES_APP_ROLE:?POSTGRES_APP_ROLE is required}"

backup_dir="$(mktemp -d)"
backup_file="${backup_dir}/synthetic.dump"
trap 'rm -rf "$backup_dir"' EXIT

source_count="$(psql "${POSTGRES_SOURCE_DSN}" -Atc \
  'SELECT count(*) FROM health_data_points')"
pg_dump --format=custom --no-owner --no-privileges \
  --dbname="${POSTGRES_SOURCE_DSN}" --file="${backup_file}"

dropdb --if-exists --force --maintenance-db="${POSTGRES_ADMIN_DSN}" \
  "${POSTGRES_RESTORE_DB}"
createdb --maintenance-db="${POSTGRES_ADMIN_DSN}" \
  --owner="${POSTGRES_APP_ROLE}" "${POSTGRES_RESTORE_DB}"
pg_restore --no-owner --no-privileges \
  --dbname="${POSTGRES_RESTORE_DSN}" "${backup_file}"

restore_count="$(psql "${POSTGRES_RESTORE_DSN}" -Atc \
  'SELECT count(*) FROM health_data_points')"
test "${source_count}" -gt 0
test "${source_count}" = "${restore_count}"
printf 'PostgreSQL backup/restore row-count validation passed (%s synthetic rows).\n' \
  "${restore_count}"
