# Prime custom_components.melitta_barista into sys.modules so that
# tests in this sub-package can import it by name even when run in
# isolation (i.e. without the rest of the suite having loaded it first).
import custom_components.melitta_barista  # noqa: F401
