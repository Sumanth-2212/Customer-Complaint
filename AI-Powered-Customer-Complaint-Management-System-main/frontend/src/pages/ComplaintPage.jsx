import ComplaintForm from "@/components/ComplaintForm";
import AIAssistant from "@/components/AIAssistant";

export default function ComplaintPage() {
  return (
    <main
      className="min-h-screen w-full bg-slate-50 px-4 md:px-6 lg:px-8 py-6"
      data-testid="complaint-page"
    >
      <div className="max-w-[1440px] mx-auto grid grid-cols-1 lg:grid-cols-10 gap-6">
        <section
          data-testid="left-panel"
          className="lg:col-span-7 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 lg:p-8"
        >
          <ComplaintForm />
        </section>
        <aside
          data-testid="right-panel"
          className="lg:col-span-3 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col min-h-[820px]"
        >
          <AIAssistant />
        </aside>
      </div>
    </main>
  );
}
