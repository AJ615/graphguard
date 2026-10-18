"""
Deterministic seed script.
Creates synthetic security data with three demo scenarios.
Safe to re-run: uses MERGE (upsert) to avoid duplicates.
"""
from __future__ import annotations
import logging
import sys
import os

# Allow running as: python -m backend.seed or python backend/seed.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.graph_db import get_graph

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

TENANT = "tenant_default"
TS = "2024-01-15T10:00:00Z"


def q(graph, cypher: str, params: dict = {}) -> None:
    try:
        graph.query(cypher, params)
    except Exception as e:
        logger.error("Query failed: %s\nCypher: %s", e, cypher[:120])


def seed(graph=None):
    if graph is None:
        graph = get_graph()

    logger.info("Seeding GraphGuard synthetic data...")

    # ── Users (10) ────────────────────────────────────────────────────────────
    users = [
        ("user_alice", "alice@corp.com", "Alice Smith", "analyst"),
        ("user_bob", "bob@corp.com", "Bob Jones", "developer"),
        ("user_carol", "carol@corp.com", "Carol White", "admin"),
        ("user_dave", "dave@corp.com", "Dave Brown", "developer"),
        ("user_eve", "eve@corp.com", "Eve Davis", "contractor"),
        ("user_frank", "frank@corp.com", "Frank Miller", "analyst"),
        ("user_grace", "grace@corp.com", "Grace Wilson", "developer"),
        ("user_henry", "henry@corp.com", "Henry Moore", "admin"),
        ("user_irene", "irene@corp.com", "Irene Taylor", "contractor"),
        ("user_jack", "jack@corp.com", "Jack Anderson", "developer"),
    ]
    for uid, email, name, role in users:
        q(graph,
          "MERGE (u:User {entity_id: $eid}) "
          "SET u.email=$email, u.name=$name, u.role=$role, u.tenant_id=$tid, u.created_at=$ts",
          {"eid": uid, "email": email, "name": name, "role": role, "tid": TENANT, "ts": TS})

    # ── Devices (12) ──────────────────────────────────────────────────────────
    devices = [
        ("dev_w001", "WORKSTATION-001", "windows", "alice"),
        ("dev_w002", "WORKSTATION-002", "windows", "bob"),
        ("dev_w003", "WORKSTATION-003", "linux", "carol"),
        ("dev_w004", "WORKSTATION-004", "macos", "dave"),
        ("dev_w005", "WORKSTATION-005", "windows", "eve"),
        ("dev_srv01", "SERVER-DB-01", "linux", "admin"),
        ("dev_srv02", "SERVER-APP-01", "linux", "admin"),
        ("dev_srv03", "SERVER-VPN-01", "linux", "admin"),
        ("dev_lap01", "LAPTOP-GRACE-01", "macos", "grace"),
        ("dev_lap02", "LAPTOP-HENRY-01", "windows", "henry"),
        ("dev_lap03", "LAPTOP-IRENE-01", "windows", "irene"),
        ("dev_mob01", "MOBILE-JACK-01", "android", "jack"),
    ]
    for did, hostname, os_, owner in devices:
        q(graph,
          "MERGE (d:Device {entity_id: $eid}) "
          "SET d.hostname=$host, d.os=$os, d.owner=$owner, d.tenant_id=$tid, d.created_at=$ts",
          {"eid": did, "host": hostname, "os": os_, "owner": owner, "tid": TENANT, "ts": TS})

    # ── IP Addresses (10) ─────────────────────────────────────────────────────
    ips = [
        ("ip_10_0_1_1", "10.0.1.1", "internal", "HQ-Office-A"),
        ("ip_10_0_1_2", "10.0.1.2", "internal", "HQ-Office-A"),
        ("ip_10_0_2_1", "10.0.2.1", "internal", "DataCenter"),
        ("ip_185_220_1", "185.220.101.1", "external", "TOR-Exit"),
        ("ip_45_33_32", "45.33.32.156", "external", "VPS-Hosting"),
        ("ip_192_168_1", "192.168.1.100", "internal", "VPN-Pool"),
        ("ip_203_0_113", "203.0.113.50", "external", "Unknown-ISP"),
        ("ip_10_0_3_1", "10.0.3.1", "internal", "DMZ"),
        ("ip_198_51_100", "198.51.100.77", "external", "Cloud-Provider"),
        ("ip_172_16_0", "172.16.0.1", "internal", "Management"),
    ]
    for iid, addr, itype, loc in ips:
        q(graph,
          "MERGE (ip:IPAddress {entity_id: $eid}) "
          "SET ip.address=$addr, ip.ip_type=$itype, ip.location=$loc, ip.tenant_id=$tid",
          {"eid": iid, "addr": addr, "itype": itype, "loc": loc, "tid": TENANT})

    # ── Services (6) ──────────────────────────────────────────────────────────
    services = [
        ("svc_hr", "HR-Portal", "web", "sensitive"),
        ("svc_fin", "Finance-API", "api", "sensitive"),
        ("svc_vpn", "Corporate-VPN", "network", "critical"),
        ("svc_email", "Email-System", "email", "standard"),
        ("svc_db", "Customer-Database", "database", "critical"),
        ("svc_git", "Internal-GitLab", "vcs", "standard"),
    ]
    for sid, name, stype, sensitivity in services:
        q(graph,
          "MERGE (s:Service {entity_id: $eid}) "
          "SET s.name=$name, s.service_type=$stype, s.sensitivity=$sensitivity, s.tenant_id=$tid",
          {"eid": sid, "name": name, "stype": stype, "sensitivity": sensitivity, "tid": TENANT})

    # ── User → Device (USED) ──────────────────────────────────────────────────
    user_device = [
        ("user_alice", "dev_w001"), ("user_bob", "dev_w002"),
        ("user_carol", "dev_w003"), ("user_dave", "dev_w004"),
        ("user_eve", "dev_w005"), ("user_grace", "dev_lap01"),
        ("user_henry", "dev_lap02"), ("user_irene", "dev_lap03"),
        ("user_jack", "dev_mob01"),
    ]
    for uid, did in user_device:
        q(graph,
          "MATCH (u:User {entity_id:$uid}), (d:Device {entity_id:$did}) "
          "MERGE (u)-[:USED]->(d)",
          {"uid": uid, "did": did})

    # ── Device → IP (CONNECTED_FROM) ─────────────────────────────────────────
    device_ip = [
        ("dev_w001", "ip_10_0_1_1"), ("dev_w002", "ip_10_0_1_2"),
        ("dev_w003", "ip_10_0_3_1"), ("dev_w004", "ip_10_0_1_1"),
        ("dev_w005", "ip_185_220_1"),   # Eve's device uses TOR Exit — suspicious
        ("dev_lap03", "ip_45_33_32"),   # Irene's laptop → VPS Hosting
        ("dev_mob01", "ip_198_51_100"), ("dev_lap01", "ip_192_168_1"),
        ("dev_lap02", "ip_172_16_0"),
    ]
    for did, iid in device_ip:
        q(graph,
          "MATCH (d:Device {entity_id:$did}), (ip:IPAddress {entity_id:$iid}) "
          "MERGE (d)-[:CONNECTED_FROM]->(ip)",
          {"did": did, "iid": iid})

    # ── User → Service (ACCESSED) ─────────────────────────────────────────────
    user_service = [
        ("user_alice", "svc_hr"), ("user_carol", "svc_hr"),
        ("user_bob", "svc_git"), ("user_dave", "svc_git"),
        ("user_frank", "svc_fin"), ("user_carol", "svc_db"),
        ("user_eve", "svc_hr"), ("user_eve", "svc_fin"),  # Eve accessed sensitive services
        ("user_irene", "svc_vpn"), ("user_grace", "svc_git"),
    ]
    for uid, sid in user_service:
        q(graph,
          "MATCH (u:User {entity_id:$uid}), (s:Service {entity_id:$sid}) "
          "MERGE (u)-[:ACCESSED]->(s)",
          {"uid": uid, "sid": sid})

    # ── Evidence (20) ─────────────────────────────────────────────────────────
    evidences = [
        ("ev_001", "auth_log", "Failed login x5 from TOR IP in 2 minutes", "confirmed"),
        ("ev_002", "network_log", "Large data transfer 1.2GB to external VPS", "confirmed"),
        ("ev_003", "endpoint_log", "Mimikatz execution detected on WORKSTATION-005", "confirmed"),
        ("ev_004", "auth_log", "Successful admin login after 5 failures from same IP", "confirmed"),
        ("ev_005", "network_log", "DNS query to known C2 domain", "confirmed"),
        ("ev_006", "endpoint_log", "PowerShell encoded command executed", "suspected"),
        ("ev_007", "auth_log", "Off-hours login at 02:34 from contractor account", "suspected"),
        ("ev_008", "network_log", "Port scan from internal host to DMZ", "suspected"),
        ("ev_009", "dlp_log", "600 customer records exported to USB", "confirmed"),
        ("ev_010", "auth_log", "Password spray attack detected — 200 accounts targeted", "confirmed"),
        ("ev_011", "endpoint_log", "Ransomware signature detected on SERVER-DB-01", "confirmed"),
        ("ev_012", "network_log", "SMB lateral movement from WORKSTATION-005", "suspected"),
        ("ev_013", "auth_log", "VPN login from unusual country", "suspected"),
        ("ev_014", "network_log", "Beaconing pattern to 185.220.101.1 every 60s", "confirmed"),
        ("ev_015", "endpoint_log", "Scheduled task created for persistence", "suspected"),
        ("ev_016", "auth_log", "MFA bypass attempt", "confirmed"),
        ("ev_017", "dlp_log", "Source code repo cloned externally", "suspected"),
        ("ev_018", "network_log", "Unusual outbound traffic on port 4444", "confirmed"),
        ("ev_019", "auth_log", "Service account used interactively", "suspected"),
        ("ev_020", "endpoint_log", "AV disabled on WORKSTATION-005", "confirmed"),
    ]
    for eid, etype, desc, status in evidences:
        q(graph,
          "MERGE (e:Evidence {entity_id:$eid}) "
          "SET e.evidence_type=$etype, e.description=$desc, e.status=$status, "
          "    e.tenant_id=$tid, e.timestamp=$ts",
          {"eid": eid, "etype": etype, "desc": desc, "status": status, "tid": TENANT, "ts": TS})

    # ── Incidents (6) ─────────────────────────────────────────────────────────
    incidents = [
        ("inc_001", "Credential Theft Campaign", "A confirmed credential theft using Mimikatz on Eve's workstation led to lateral movement.", "confirmed", 0.95),
        ("inc_002", "Data Exfiltration — Customer Records", "600 customer records exported to USB from HR Portal.", "confirmed", 0.90),
        ("inc_003", "Ransomware Deployment Attempt", "Ransomware signature on DB server — contained before encryption.", "confirmed", 0.88),
        ("inc_004", "Password Spray Attack", "200 accounts targeted in coordinated spray from TOR exit node.", "confirmed", 0.92),
        ("inc_005", "Suspicious Contractor Activity", "Off-hours access by contractor to sensitive financial service.", "suspected", 0.60),
        ("inc_006", "Internal Port Scan", "Internal host conducted DMZ port scan — likely reconnaissance.", "suspected", 0.55),
    ]
    for iid, name, desc, status, conf in incidents:
        q(graph,
          "MERGE (i:Incident {entity_id:$eid}) "
          "SET i.name=$name, i.description=$desc, i.status=$status, "
          "    i.confidence=$conf, i.tenant_id=$tid, i.timestamp=$ts",
          {"eid": iid, "name": name, "desc": desc, "status": status, "conf": conf, "tid": TENANT, "ts": TS})

    # ── Alerts (12) ───────────────────────────────────────────────────────────
    alerts = [
        # Scenario A: Alert connected to confirmed incident via device
        ("alert_001", "TOR Exit Node Connection", "critical", "network_anomaly", "dev_w005", "user_eve"),
        ("alert_002", "Mimikatz Detection", "critical", "malware", "dev_w005", "user_eve"),
        # Scenario B: Suspicious alert with no corroborating graph path
        ("alert_003", "Off-Hours Admin Login", "medium", "auth_anomaly", "dev_w003", "user_carol"),
        # Scenario C: Related alert for cross-session memory test
        ("alert_004", "SMB Lateral Movement", "high", "network_anomaly", "dev_w005", "user_eve"),
        # Additional alerts for richness
        ("alert_005", "Data Exfiltration Detected", "high", "dlp", "dev_w001", "user_alice"),
        ("alert_006", "Password Spray from TOR", "critical", "auth_anomaly", "dev_w005", "user_eve"),
        ("alert_007", "Ransomware Signature Match", "critical", "malware", "dev_srv01", "user_carol"),
        ("alert_008", "Unusual VPN Login", "medium", "auth_anomaly", "dev_srv03", "user_irene"),
        ("alert_009", "Port Scan DMZ", "medium", "network_anomaly", "dev_w002", "user_bob"),
        ("alert_010", "MFA Bypass Attempt", "high", "auth_anomaly", "dev_lap03", "user_irene"),
        ("alert_011", "Beaconing C2 Pattern", "critical", "network_anomaly", "dev_w005", "user_eve"),
        ("alert_012", "Source Code Exfiltration", "high", "dlp", "dev_lap02", "user_henry"),
    ]
    for aid, name, severity, atype, device, user in alerts:
        q(graph,
          "MERGE (a:Alert {entity_id:$eid}) "
          "SET a.name=$name, a.severity=$severity, a.alert_type=$atype, "
          "    a.device_id=$did, a.user_id=$uid, a.tenant_id=$tid, a.timestamp=$ts, a.status='open'",
          {"eid": aid, "name": name, "severity": severity, "atype": atype,
           "did": device, "uid": user, "tid": TENANT, "ts": TS})

    # ── Alert relationships ────────────────────────────────────────────────────
    # Alert → User (TRIGGERED)
    alert_user = [
        ("alert_001", "user_eve"), ("alert_002", "user_eve"),
        ("alert_003", "user_carol"), ("alert_004", "user_eve"),
        ("alert_005", "user_alice"), ("alert_006", "user_eve"),
        ("alert_007", "user_carol"), ("alert_008", "user_irene"),
        ("alert_009", "user_bob"), ("alert_010", "user_irene"),
        ("alert_011", "user_eve"), ("alert_012", "user_henry"),
    ]
    for aid, uid in alert_user:
        q(graph,
          "MATCH (a:Alert {entity_id:$aid}), (u:User {entity_id:$uid}) "
          "MERGE (u)-[:TRIGGERED]->(a)",
          {"aid": aid, "uid": uid})

    # Alert → Device (INVOLVED_IN via Device)
    alert_device = [
        ("dev_w005", "alert_001"), ("dev_w005", "alert_002"),
        ("dev_w003", "alert_003"), ("dev_w005", "alert_004"),
        ("dev_w001", "alert_005"), ("dev_w005", "alert_006"),
        ("dev_srv01", "alert_007"), ("dev_srv03", "alert_008"),
        ("dev_w002", "alert_009"), ("dev_lap03", "alert_010"),
        ("dev_w005", "alert_011"), ("dev_lap02", "alert_012"),
    ]
    for did, aid in alert_device:
        q(graph,
          "MATCH (d:Device {entity_id:$did}), (a:Alert {entity_id:$aid}) "
          "MERGE (d)-[:INVOLVED_IN]->(a)",
          {"did": did, "aid": aid})

    # ── Alert → Incident (ASSOCIATED_WITH) ───────────────────────────────────
    alert_incident = [
        ("alert_001", "inc_001"), ("alert_002", "inc_001"),
        ("alert_004", "inc_001"), ("alert_006", "inc_004"),
        ("alert_007", "inc_003"), ("alert_011", "inc_001"),
        ("alert_005", "inc_002"),
    ]
    for aid, iid in alert_incident:
        q(graph,
          "MATCH (a:Alert {entity_id:$aid}), (i:Incident {entity_id:$iid}) "
          "MERGE (a)-[:ASSOCIATED_WITH]->(i)",
          {"aid": aid, "iid": iid})

    # ── Incident → Evidence (SUPPORTED_BY) ───────────────────────────────────
    incident_evidence = [
        ("inc_001", "ev_001"), ("inc_001", "ev_003"), ("inc_001", "ev_012"),
        ("inc_001", "ev_014"), ("inc_001", "ev_020"),
        ("inc_002", "ev_009"), ("inc_003", "ev_011"),
        ("inc_004", "ev_010"), ("inc_004", "ev_016"),
        ("inc_005", "ev_007"), ("inc_006", "ev_008"),
    ]
    for iid, eid in incident_evidence:
        q(graph,
          "MATCH (i:Incident {entity_id:$iid}), (e:Evidence {entity_id:$eid}) "
          "MERGE (i)-[:SUPPORTED_BY]->(e)",
          {"iid": iid, "eid": eid})

    # ── Alert → Evidence (SUPPORTED_BY) ──────────────────────────────────────
    alert_evidence = [
        ("alert_001", "ev_001"), ("alert_002", "ev_003"),
        ("alert_004", "ev_012"), ("alert_006", "ev_010"),
        ("alert_011", "ev_014"), ("alert_002", "ev_020"),
        ("alert_005", "ev_009"), ("alert_007", "ev_011"),
    ]
    for aid, eid in alert_evidence:
        q(graph,
          "MATCH (a:Alert {entity_id:$aid}), (e:Evidence {entity_id:$eid}) "
          "MERGE (a)-[:SUPPORTED_BY]->(e)",
          {"aid": aid, "eid": eid})

    # ── SCENARIO A: Connected risk chain ─────────────────────────────────────
    # dev_w005 → inc_001 (key multi-hop link for scenario A)
    q(graph,
      "MATCH (d:Device {entity_id:'dev_w005'}), (i:Incident {entity_id:'inc_001'}) "
      "MERGE (d)-[:INVOLVED_IN]->(i)")

    # inc_001 → svc_fin (sensitive service tie)
    q(graph,
      "MATCH (i:Incident {entity_id:'inc_001'}), (s:Service {entity_id:'svc_fin'}) "
      "MERGE (i)-[:TARGETED]->(s)")

    # ── SCENARIO B: No historical relationship from dev_w003 ─────────────────
    # (dev_w003 belongs to Carol, separate network segment — no incident link)
    # This is achieved by NOT creating a dev_w003 → incident link above.

    # ── SCENARIO C: Related alert pair for cross-session memory ──────────────
    # alert_001 and alert_004 share dev_w005 and inc_001
    q(graph,
      "MATCH (a1:Alert {entity_id:'alert_001'}), (a2:Alert {entity_id:'alert_004'}) "
      "MERGE (a1)-[:RELATED_TO]->(a2)")

    logger.info("Seed complete. Synthetic data loaded successfully.")
    return True


def reset_and_seed(graph=None):
    """Development-only: delete all nodes/edges then re-seed."""
    if graph is None:
        graph = get_graph()
    logger.warning("RESETTING graph — deleting all data.")
    try:
        graph.query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        logger.error("Reset failed: %s", e)
    seed(graph)


if __name__ == "__main__":
    import sys
    if "--reset" in sys.argv:
        reset_and_seed()
    else:
        seed()
