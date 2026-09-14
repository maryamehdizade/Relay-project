export async function login(
  username: string,
  password: string,
) {
  const response = await fetch(
    "http://localhost:8000/api/auth/login/",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    },
  );

  console.log(
    "STATUS:",
    response.status,
  );

  const data = await response.json();

  console.log(
    "DATA:",
    data,
  );

  if (!response.ok) {
    throw new Error("Login failed");
  }

  return data;
}
export async function getMessages(
  conversationId: number,
  token: string,
) {
  const response = await fetch(
    `http://localhost:8000/api/conversations/${conversationId}/messages/`,
    {
      method: "GET",
      headers: {
        Authorization: `Token ${token}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      "Failed to load messages",
    );
  }

  return response.json();
}