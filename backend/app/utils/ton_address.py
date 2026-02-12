from tonsdk.utils import Address


def validate_ton_address(value: str) -> str:
    try:
        address = Address(value)
        return address.to_string(True, is_bounceable=True)
    except Exception as exc:
        raise ValueError(f"Invalid TON address: {value!r}") from exc
