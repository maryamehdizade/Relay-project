interface ActivityPanelProps {
  activities: Activity[];
}
interface Activity {
  message: string;
  status?: string;
}

function ActivityPanel({
  activities,
}: ActivityPanelProps) {

  return (
    <section>
      <h3>
        AI Activity
      </h3>

      {
        activities.length === 0 ? (
          <p>
            Waiting for activity...
          </p>
        ) : (
          activities.map(
            (activity, index) => (
              <p key={index}>
                {
                  activity.status === "completed"
                    ? "✅"
                    : activity.status === "running"
                    ? "🔎"
                    : "🔹"
                }
              
                {" "}
              
                {activity.message}
              </p>
            ),
          )
        )
      }

    </section>
  );
}


export default ActivityPanel;