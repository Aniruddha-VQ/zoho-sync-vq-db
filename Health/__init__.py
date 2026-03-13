import base64
import json
import os
import struct
import sys

import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    details = {
        "status": "ok",
        "python_version": sys.version,
    }

    # If ?diag=token is passed, decode the managed identity token claims
    if req.params.get("diag") == "token":
        try:
            from azure.identity import ManagedIdentityCredential

            credential = ManagedIdentityCredential()
            token = credential.get_token("https://database.windows.net/.default")
            # Decode JWT payload (second segment)
            parts = token.token.split(".")
            payload_b64 = parts[1] + "=="  # pad for base64
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            claims = json.loads(payload_bytes)
            details["token_claims"] = {
                "oid": claims.get("oid"),
                "sub": claims.get("sub"),
                "appid": claims.get("appid"),
                "aud": claims.get("aud"),
                "tid": claims.get("tid"),
                "xms_mirid": claims.get("xms_mirid"),
            }
        except Exception as exc:
            details["token_error"] = str(exc)

    # If ?diag=db is passed, try connecting to the database
    if req.params.get("diag") == "db":
        import pyodbc
        from azure.identity import ManagedIdentityCredential

        sql_server = os.getenv("SQL_SERVER", "")
        sql_database = os.getenv("SQL_DATABASE", "")
        sql_port = os.getenv("SQL_PORT", "1433")
        driver = os.getenv("SQL_ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

        conn_str = (
            f"Driver={{{driver}}};"
            f"Server=tcp:{sql_server},{sql_port};"
            f"Database={sql_database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )
        details["conn_str_masked"] = conn_str
        details["pyodbc_version"] = pyodbc.version
        details["odbc_drivers"] = pyodbc.drivers()

        # Try token-based auth
        try:
            credential = ManagedIdentityCredential()
            token = credential.get_token("https://database.windows.net/.default")
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(
                f"<I{len(token_bytes)}s", len(token_bytes), token_bytes
            )
            conn = pyodbc.connect(
                conn_str, attrs_before={1256: token_struct}, autocommit=False
            )
            cur = conn.cursor()
            cur.execute("SELECT 1 AS test, SUSER_SNAME() AS login_name, DB_NAME() AS db")
            row = cur.fetchone()
            details["db_test"] = {
                "success": True,
                "test": row[0],
                "login_name": row[1],
                "db_name": row[2],
            }
            conn.close()
        except Exception as exc:
            details["db_test"] = {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

        # Also try ActiveDirectoryMsi as fallback test
        try:
            msi_conn_str = conn_str + "Authentication=ActiveDirectoryMsi;"
            conn2 = pyodbc.connect(msi_conn_str, autocommit=False)
            cur2 = conn2.cursor()
            cur2.execute("SELECT 1 AS test, SUSER_SNAME() AS login_name")
            row2 = cur2.fetchone()
            details["db_test_msi"] = {
                "success": True,
                "login_name": row2[1],
            }
            conn2.close()
        except Exception as exc:
            details["db_test_msi"] = {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    return func.HttpResponse(
        json.dumps(details),
        status_code=200,
        mimetype="application/json",
    )
