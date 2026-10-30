# Architecture
CSV generator -> validation -> rule engine -> FastAPI -> SQLite event/history tables -> lightweight browser dashboard.
Ground-truth labels are generated separately and excluded from detector inputs. `configuration_hash` makes each simulation configuration traceable. Historical simulation runs and alarms are appended rather than overwriting prior records.
