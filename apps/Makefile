# ######################################################################## #
# ### TEMPORAL APP ### #
# ######################################################################## #
.PHONY: run_temporal_app stop_temporal_app temporal_app_refress_inputDataset check_control_yaml
CONTAINER_TEMPORALL_APP_NAME = mds_temporal
# Prefer VARIANT, keep df for backward compatibility
DEFAULT_DATASET := $(if $(VARIANT),$(VARIANT),$(df))
# Prefer EPOCH_MODE, keep em for backward compatibility
EPOCH_MODE := $(if $(EPOCH_MODE),$(EPOCH_MODE),$(em))

run_temporal_app:
	@cd temporal_app && VARIANT=$(DEFAULT_DATASET) EPOCH_MODE=$(EPOCH_MODE) docker compose -f docker-compose.yml up -d

stop_temporal_app:
	@cd temporal_app && docker compose down

# 
temporal_app_refress_inputDataset:
	@docker exec ${CONTAINER_TEMPORALL_APP_NAME} python generate_control_yml.py

check_control_yaml:
	@docker exec -it ${CONTAINER_TEMPORALL_APP_NAME} cat control.yml


# ######################################################################## #
# ### WINDOWS APP ### #
# ######################################################################## #
.PHONY: run_windows_app stop_windows_app

# Prefer VARIANT, keep ws for backward compatibility
WINDOWS_VERSION := $(if $(VARIANT),$(VARIANT),$(ws))

run_windows_app:
	@cd windows_app && WINDOW_VERSION=$(WINDOWS_VERSION) docker compose -f docker-compose.yml up -d

stop_windows_app:
	@cd windows_app && docker compose -f docker-compose.yml down