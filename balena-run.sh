#!/bin/bash

set -eu
declare -a MAIN_ARGS
export TZ="${TZ:-Europe/London}"
readonly CONFIG_FILE="config.json"


function require_env() {
  # Requires that ${envname} is set, with a nicer error than ${envname?}
  #
  # Usage: require_env envname
  set +u
  if [[ -z "${!1}" ]]; then
    echo "Required environment variable \"${1}\" is not set." >&2
    exit 1
  fi
}


function required_arg() {
  # Add required argument from an environment variable.
  #
  # Usage: required_arg argname envname
  require_env "${2}"
  MAIN_ARGS+=( --"${1}"="${!2}" )
}


function optional_arg() {
  # Add optional argument from an environment variable, with optional default.
  #
  # Usage: optional_arg argname envname [default]
  if [[ -n "${!2}" ]]; then
    required_arg "$@"
  elif [[ -n "${3}" ]]; then
    MAIN_ARGS+=( --"${1}"="${3}" )
  fi
}


function prepare_config() {
  # Set up the JSON config for the service if it does not already exist.
  if [[ -f "${CONFIG_FILE}" ]]; then
    return
  fi

  require_env transportApi_appId
  require_env transportApi_apiKey

  # Place these into a config file for convenience.
  jq -n '{transport_api: {app_id: $app_id, api_key: $api_key}}' \
    --arg app_id "${transportApi_appId}" \
    --arg api_key "${transportApi_apiKey}" \
    > "${CONFIG_FILE}"
}


function prepare_args() {
  # Required. Departure station.
  required_arg depart_from departFrom

  # Optional. One or more time ranges during which the display will show data.
  optional_arg active_times activeTimes

  # Optional. One or more time ranges during which the display will be entirely
  # blank.
  optional_arg blank_times blankTimes

  # Optional. One or more National Rail station codes that services must call
  # at, e.g. `BFR` or `BFR,CTK`.
  optional_arg calling_at callingAt

  # Optional. How much to rotate the display; either `0` or `180`.
  optional_arg display_rotation displayRotation 0

  # Optional. If greater than zero, trains departing in less than this many
  # minutes are not shown.
  optional_arg min_departure_min minDepartureMin 0

  # Optional. Name shown when current time is outside active hours.
  optional_arg out_of_hours_name outOfHoursName

  # Optional. If a train calls at a station in this list, it is marked "slow".
  optional_arg slow_stations slowStations

  # Optional. Seconds between data refresh, during active hours.
  optional_arg refresh_interval refreshTime 120
}


function main() {
  prepare_config
  prepare_args
  exec python ./src/main.py "${MAIN_ARGS[@]}" "$@"
}


main "$@"
