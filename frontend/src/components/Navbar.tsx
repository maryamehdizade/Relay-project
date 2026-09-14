import { Link, useNavigate } from "react-router-dom";


function Navbar() {

  const navigate = useNavigate();


  function logout() {
    localStorage.removeItem("token");
    navigate("/login");
  }


  return (
    <nav>

      <Link to="/chat">
        Chat
      </Link>

      {" | "}

      <Link to="/documents">
        Documents
      </Link>

      {" | "}

      <button onClick={logout}>
        Logout
      </button>

    </nav>
  );
}


export default Navbar;