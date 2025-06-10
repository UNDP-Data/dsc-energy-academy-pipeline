type KeyResourcesModule = {
  content: {
    title: string;
    resources: Array<{
      image: string;
      href: string;
      text: string;
    }>;
  };
};

type KeyTakeawaysModule = {
  content: {
    title: string;
    intro: string;
    takeaways: Array<{
      image: string;
      title: string;
      description: string;
    }>;
  };
};

type LearningObjectivesModule = {
  content: {
    title: string;
    intro: string;
    takeaways: Array<{
      image: string;
      title: string;
      description: string;
    }>;
  };
};

type ListOfLessonsModule = {
  content: {
    title: string;
    lessons: Array<{
      image: string;
      title: string;
      type: "lesson" | "quiz";
      state: "completed" | "in_progress" | "todo";
    }>;
  };
};

type ModuleChapterOutroModule = {
  content: {
    intro: string;
    title: {
      first_line: string;
      second_line: string;
    };
    subtitle: string;
    body: string;
    quiz: {
      intro: string;
      title: string;
      cta: string;
      buttonCta: string;
      image: string;
    };
  };
};
