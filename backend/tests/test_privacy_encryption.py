import pytest
import sqlite3
import os
from utils.encryption import (
    encrypt_pii, decrypt_pii, mask_name, mask_id_card, mask_phone, compute_age_group
)
from utils.local_store import LocalStore, DB_PATH
from routers.organization import get_org_members_endpoint

def test_encryption_and_decryption_pii():
    plaintext = "310101199001011234"
    enc = encrypt_pii(plaintext)
    assert enc != plaintext
    assert enc.startswith("enc:v1:")
    # Idempotent encrypt
    assert encrypt_pii(enc) == enc
    # Decrypt
    dec = decrypt_pii(enc)
    assert dec == plaintext
    # Decrypt plaintext backward compatibility
    assert decrypt_pii("raw_old_data") == "raw_old_data"
    assert decrypt_pii("") == ""
    assert decrypt_pii(None) is None

def test_masking_helpers():
    # Names
    assert mask_name("李") == "李"
    assert mask_name("张三") == "张*"
    assert mask_name("陈晓韵") == "陈*韵"
    assert mask_name("欧阳六六") == "欧**六"
    
    # ID Card
    assert mask_id_card("310101199001011234") == "310101********1234"
    assert mask_id_card("") == ""
    
    # Phone
    assert mask_phone("13812345678") == "138****5678"
    assert mask_phone("") == ""

def test_compute_age_group_domain_rules():
    # Age group must NEVER be 精英 (which is reserved for PB tier)
    # >= 50: 大师组
    assert compute_age_group("1970-01-01") == "大师组"
    # 40-49: 壮年组
    assert compute_age_group("1980-05-12") == "壮年组"
    # 30-39: 中坚组
    assert compute_age_group("1992-10-20") == "中坚组"
    # < 30: 青年组
    assert compute_age_group("2002-03-15") == "青年组"
    assert compute_age_group(None) == "未填"
    # Works even if encrypted
    enc_dob = encrypt_pii("1982-08-08")
    assert compute_age_group(enc_dob) == "壮年组"

def test_profile_and_org_privacy_lifecycle():
    test_uid = "u_test_privacy_runner_999"
    test_org_id = "org_fudan_gobi"

    # 1. Upsert profile with sensitive PII
    LocalStore.upsert_profile(test_uid, {
        "display_name": "测试隐私跑者",
        "real_name": "张无忌",
        "id_card": "110101198505051234",
        "phone": "13912345678",
        "date_of_birth": "1985-05-05",
        "garmin_connected": 1,
        "garmin_email": "runner@garmin.test"
    })

    # 2. Check raw database storage is encrypted
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT real_name, id_card, phone, date_of_birth FROM profiles WHERE id = ?", (test_uid,))
        row = dict(cur.fetchone())
        assert row["real_name"].startswith("enc:v1:")
        assert row["id_card"].startswith("enc:v1:")
        assert row["phone"].startswith("enc:v1:")
        assert row["date_of_birth"].startswith("enc:v1:")

    # 3. Reading through LocalStore decrypts it
    p = LocalStore.get_profile(test_uid)
    assert p["real_name"] == "张无忌"
    assert p["id_card"] == "110101198505051234"
    assert p["phone"] == "13912345678"
    assert p["date_of_birth"] == "1985-05-05"

    # 4. Join organization with sensitive details
    join_res = LocalStore.join_organization(
        user_id=test_uid,
        invite_code="FDGOBI",
        real_name="张无忌",
        gender="male",
        date_of_birth="1985-05-05",
        class_name="EMBA 25秋",
        phone="13912345678",
        id_card="110101198505051234"
    )
    assert join_res["real_name"] == "张无忌"

    # Check org_members table column is encrypted
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT real_name, id_card, phone, date_of_birth FROM organization_members WHERE user_id = ? AND org_id = ?", (test_uid, test_org_id))
        om_row = cur.fetchone()
        assert om_row[0].startswith("enc:v1:") # real_name
        assert om_row[1].startswith("enc:v1:") # id_card
        assert om_row[2].startswith("enc:v1:") # phone
        assert om_row[3].startswith("enc:v1:") # date_of_birth

    # 5. Non-admin accessing org members endpoint receives masked name, no phone, no id_card
    non_admin_res = get_org_members_endpoint(test_org_id, operator_uid="other_user_stranger")
    target_member = next((m for m in non_admin_res["members"] if m["user_id"] == test_uid), None)
    assert target_member is not None
    assert target_member["real_name"] == "张*忌" # Masked!
    assert "id_card" not in target_member
    assert "phone" not in target_member
    assert "date_of_birth" not in target_member
    assert target_member["age_group"] == "壮年组"

    # 6. Org admin accessing gets real name, masked phone and masked id_card
    admin_res = get_org_members_endpoint(test_org_id, operator_uid="u_df65d9a588c9")
    target_admin_view = next((m for m in admin_res["members"] if m["user_id"] == test_uid), None)
    assert target_admin_view is not None
    assert target_admin_view["real_name"] == "张无忌"
    assert target_admin_view["phone"] == "139****5678"
    assert target_admin_view["id_card"] == "110101********1234"

    # 7. One-click purge privacy data
    purge_res = LocalStore.purge_user_privacy_data(test_uid)
    assert purge_res["success"] is True

    # Verify profile is wiped
    purged_p = LocalStore.get_profile(test_uid)
    assert purged_p["real_name"] == ""
    assert purged_p["id_card"] == ""
    assert purged_p["phone"] == ""
    assert purged_p["date_of_birth"] == ""
    assert purged_p["garmin_connected"] == 0
    assert purged_p["display_name"].startswith("跑者_")

    # Verify org membership was removed
    user_orgs = LocalStore.get_user_organizations(test_uid)
    assert len(user_orgs) == 0

    # Clean up test user
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (test_uid,))
        conn.execute("DELETE FROM organization_members WHERE user_id = ?", (test_uid,))
