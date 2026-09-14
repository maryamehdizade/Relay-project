import { useEffect, useState } from "react";


const API_URL = "http://localhost:8000";


interface Document {
  id: number;
  name: string;
  indexed: boolean;
}


function Documents() {

  const token =
    localStorage.getItem("token") || "";


  const [documents, setDocuments] =
    useState<Document[]>([]);


  useEffect(() => {

    async function loadDocuments() {

      const response = await fetch(
        `${API_URL}/api/documents/`,
        {
          headers: {
            Authorization:
              `Token ${token}`,
          },
        },
      );


      if (!response.ok) {
        return;
      }


      const data =
        await response.json();


      setDocuments(data);
    }


    loadDocuments();

  }, []);


  return (
    <main>

      <h1>
        Documents
      </h1>


      {
        documents.length === 0 ? (
          <p>
            No documents uploaded.
          </p>
        ) : (
          documents.map((document) => (
            <div key={document.id}>

              <strong>
                {document.name}
              </strong>

              <p>
                Indexed:
                {" "}
                {document.indexed
                  ? "Yes"
                  : "Processing"}
              </p>

            </div>
          ))
        )
      }

    </main>
  );
}


export default Documents;