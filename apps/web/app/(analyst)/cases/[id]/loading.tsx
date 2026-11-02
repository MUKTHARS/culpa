import { Card } from "@/components/ui/Card/Card";
import { Loader } from "@/components/ui/Loader/Loader";

/** Shown at once while a case page loads (for example right after a dispute is opened). */
export default function CaseLoading() {
  return (
    <Card title="Opening the case">
      <Loader label="Loading the dispute and Culpa's analysis…" />
    </Card>
  );
}
