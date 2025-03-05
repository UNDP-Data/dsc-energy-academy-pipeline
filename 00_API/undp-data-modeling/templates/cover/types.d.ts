type C1Module = {
  content: {
    image: string;
    lessonId: string;
    intro: string;
    title: string;
    cta: string;
  };
};

type CoverCaseStudyModule = {
  colorscheme: "light" | "dark";
  content: {
    image: {
      src: string;
      caption: string;
    };
    intro: string;
    title: string;
  };
};

type CoverPartModule = {
  colorscheme: "light" | "dark";
  content: {
    image: string;
    intro: string;
    title: string;
  };
};

type CoverSubpartModule = {
  colorscheme: "light" | "dark";
  content: {
    image: {
      src: string;
      caption: string;
    };
    intro: string;
    title: string;
  };
};

type L1Module = {
  content: {
    image: string;
    lessonId: string;
    intro: string;
    title: string;
  };
};

type M1Module = {
  content: {
    image: string;
    lessonId: string;
    title: string;
    cta: string;
  };
};
