import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/client";


function Login() {
  const navigate = useNavigate();

  const [username, setUsername] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [error, setError] =
    useState("");


  async function handleLogin() {
    try {
      const data = await login(
        username,
        password,
      );

      localStorage.setItem(
        "token",
        data.token,
      );

      navigate("/chat");

    } catch {
      setError(
        "Invalid username or password",
      );
    }
  }


  return (
    <main>
      <h1>
        Relay Login
      </h1>

      <input
        placeholder="username"
        value={username}
        onChange={(e) =>
          setUsername(e.target.value)
        }
      />

      <input
        type="password"
        placeholder="password"
        value={password}
        onChange={(e) =>
          setPassword(e.target.value)
        }
      />

      <button
        onClick={handleLogin}
      >
        Login
      </button>

      {
        error && (
          <p>
            {error}
          </p>
        )
      }

    </main>
  );
}

export default Login;