"""Server firewall leases are independent from the client cutover lease."""
import ipaddress
import time

from .core import digest, read_json, require, write_private
from .remote import call


def private_access(config, *, include_observed=False):
    management = config.get("management", {})
    require(management.get("console_recovery_verified") is True and config.get("ssh", {}).get("user") != "root",
            "recovery_unproven", "Verify provider-console recovery and a nonroot SSH account before closing public management.")
    addresses = management.get("addresses", [])
    require(bool(addresses), "missing_tailscale", "Supply verified server Tailscale addresses.")
    observed = None
    for value in addresses:
        ip = ipaddress.ip_address(value)
        network = ipaddress.ip_network("100.64.0.0/10" if ip.version == 4 else "fd7a:115c:a1e0::/48")
        require(ip in network, "invalid_tailscale", "Management address is outside the Tailscale range.")
        # Fresh SSH with the same pinned host key, no multiplexing.
        result = call(config, "inspect", host_override=value)
        if observed is None:
            observed = result
    return (addresses, observed) if include_observed else addresses


def public_families(config, observed):
    require(isinstance(observed.get("public_addresses"), list), "missing_evidence",
            "Inspect the server's assigned addresses before deciding which public SSH checks apply.")
    values = [config["server"]["address"], *observed["public_addresses"],
              *config.get("management", {}).get("public_addresses", [])]
    try:
        return {ipaddress.ip_address(value).version for value in values}
    except ValueError:
        require(False, "invalid_address", "Management public addresses must be explicit IPv4 or IPv6 addresses.")


def plan(store, profile):
    config = store.load(profile)
    private_access(config)
    value = {"profile_digest": digest(config), "created": time.time(),
             "changes": ["Prove server-owned firewall restoration", "Arm a 10-minute server rollback",
                         "Allow SSH on tailscale0 and remove only the owned public bootstrap SSH rule",
                         "Retain TCP443/UDP443 and Tailscale transport"]}
    write_private(store.profile(profile) / "management-plan.json", value)
    return {"phase": "needs_user_action", "plan_digest": digest(value), "changes": value["changes"]}


def apply(store, profile, approved_digest):
    config = store.load(profile)
    p = read_json(store.profile(profile) / "management-plan.json")
    require(digest(p) == approved_digest and p["profile_digest"] == digest(config) and time.time() - p["created"] < 1800,
            "stale_plan", "Review a fresh management plan.")
    addresses = private_access(config)
    result = call(config, "harden", host_override=addresses[0], timeout=60)
    write_private(store.profile(profile) / "management-lease.json", result)
    # Public SSH is intentionally unavailable now. All follow-up uses the pinned private address.
    call(config, "inspect", host_override=addresses[0])
    return {"phase": "testing", "server_lease": result["id"],
            "next": "Verify direct public SSH denial and BOTH proxy protocols before management commit. Server rollback is still armed."}


def finish(store, profile, *, commit=False, evidence=None):
    config = store.load(profile)
    addresses, observed = private_access(config, include_observed=True)
    lease = read_json(store.profile(profile) / "management-lease.json")
    if commit:
        require(evidence is not None, "missing_evidence", "Direct public SSH denial evidence is required for the server's assigned address families.")
        e = read_json(evidence)
        require(e.get("profile_digest") == digest(config) and
                lease["deadline"] - 600 <= e.get("observed_at", 0) <= time.time() and
                time.time() - e.get("observed_at", 0) < 300,
                "missing_evidence", "Public SSH denial evidence must be fresh and bound to this profile.")
        for family in public_families(config, observed):
            require(e.get("public_ipv" + str(family) + "_ssh_blocked") is True,
                    "missing_evidence", "Directly verify public SSH denial for every assigned address family; do not invent an absent-family result.")
        protocols = store.state(profile).get("protocol_checks", {})
        for protocol in ["reality", "hysteria2"]:
            result = protocols.get(protocol, {})
            require(result.get("observed_at", 0) >= lease["deadline"] - 600 and
                    result.get("checks") and all(result["checks"].values()),
                    "verification_missing", "Both protocols must pass fresh isolated checks after management restriction.")
    result = call(config, "harden_commit" if commit else "harden_rollback", {"lease": lease["id"]}, host_override=addresses[0])
    write_private(store.profile(profile) / "management-lease.json", result)
    if commit:
        state = store.state(profile)
        checks = {**state.get("checks", {}), "tailscale_ssh": True, "public_ssh_blocked": True}
        store.update(profile, checks=checks)
    return {"phase": result["phase"], "scope": "server firewall only"}
