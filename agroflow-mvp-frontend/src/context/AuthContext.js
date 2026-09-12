import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getCurrentIdentity,
  login as loginRequest,
} from "../api/authApi";


export const AuthContext = createContext(null);


function getVerifiedMemberships(identity) {

  return (identity?.memberships || []).filter(
    (membership) =>
      membership?.status === "ACTIVE" &&
      membership?.organization?.status === "ACTIVE" &&
      membership?.organization?.verification_status ===
        "VERIFIED"
  );
}


function getPendingMemberships(identity) {

  return (identity?.memberships || []).filter(
    (membership) =>
      membership?.status === "PENDING" ||
      membership?.organization?.verification_status ===
        "PENDING"
  );
}


function getRejectedMemberships(identity) {

  return (identity?.memberships || []).filter(
    (membership) =>
      membership?.status === "REJECTED" ||
      membership?.organization?.verification_status ===
        "REJECTED"
  );
}


function deriveWorkspace(identity) {

  if (
    identity?.user?.is_system_admin === true
  ) {
    return "admin";
  }

  const memberships =
    getVerifiedMemberships(identity);

  if (memberships.length !== 1) {
    return null;
  }

  const type =
    memberships[0]?.organization?.organization_type;

  if (type === "SCHOOL") {
    return "school";
  }

  if (type === "SUPPLIER") {
    return "supplier";
  }

  return null;
}


export function AuthProvider({
  children,
}) {

  const [authenticated, setAuthenticated] = useState(false);

  const [identity, setIdentity] =
    useState(null);

  const [loading, setLoading] =
    useState(true);


  async function loadIdentity() {

    const value =
      await getCurrentIdentity();

    setIdentity(value);

    return value;
  }


  async function login(
    email,
    password
  ) {

    await loginRequest(email, password);
    setAuthenticated(true);
    await loadIdentity();
  }


  async function logout() {
    try {
      const { logout: logoutRequest } = await import("../api/authApi");
      await logoutRequest();
    } finally {
      setAuthenticated(false);
      setIdentity(null);
    }
  }


  useEffect(() => {
    loadIdentity()
      .then(() => setAuthenticated(true))
      .catch(() => { setAuthenticated(false); setIdentity(null); })
      .finally(() => setLoading(false));
  }, []);


  const value = useMemo(() => {

    const memberships =
      identity?.memberships || [];

    const verifiedMemberships =
      getVerifiedMemberships(
        identity
      );

    const pendingMemberships =
      getPendingMemberships(
        identity
      );

    const rejectedMemberships =
      getRejectedMemberships(
        identity
      );

    return {


      identity,

      user:
        identity?.user || null,

      memberships,

      verifiedMemberships,

      pendingMemberships,

      rejectedMemberships,

      workspace:
        deriveWorkspace(identity),

      isSystemAdmin:
        identity?.user?.is_system_admin === true,

      isAuthenticated:
        Boolean(authenticated && identity),

      hasVerifiedOrganization:
        verifiedMemberships.length > 0,

      hasPendingVerification:
        pendingMemberships.length > 0,

      hasRejectedVerification:
        rejectedMemberships.length > 0,

      loading,

      login,

      logout,
    };

  }, [
    authenticated,
    identity,
    loading,
  ]);


  return (
    <AuthContext.Provider
      value={value}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth() {

  return useContext(
    AuthContext
  );
}