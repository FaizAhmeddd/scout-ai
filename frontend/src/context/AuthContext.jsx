import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { authApi } from "../services/api.js";
import { errorStatus, setUnauthorizedHandler, tokenStore } from "../services/apiClient.js";

const AuthContext = createContext(null);

export const SESSION_EXPIRED = "Your session has expired. Please sign in again to continue.";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));
  // Set when the session could not be restored because the server was unreachable (token is kept).
  const [sessionError, setSessionError] = useState(null);
  // One-shot message shown on the login page (e.g. after the token expired).
  const [notice, setNotice] = useState(null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setSessionError(null);
  }, []);

  const expire = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setSessionError(null);
    setNotice(SESSION_EXPIRED);
  }, []);

  const restore = useCallback(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setSessionError(null);
    authApi
      .me()
      .then((me) => setUser(me))
      .catch((err) => {
        if (errorStatus(err) === 401) expire();
        else setSessionError(err);
      })
      .finally(() => setLoading(false));
  }, [expire]);

  useEffect(() => {
    setUnauthorizedHandler(expire);
    restore();
  }, [expire, restore]);

  const authenticate = useCallback((response) => {
    if (!response?.access_token || !response?.user) throw new Error("Unexpected response from the server. Please try again.");
    tokenStore.set(response.access_token);
    setUser(response.user);
    setNotice(null);
    setSessionError(null);
    return response.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      sessionError,
      notice,
      clearNotice: () => setNotice(null),
      retrySession: restore,
      login: (credentials) => authApi.login(credentials).then(authenticate),
      signup: (details) => authApi.signup(details).then(authenticate),
      logout,
    }),
    [user, loading, sessionError, notice, restore, authenticate, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
