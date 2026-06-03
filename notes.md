
#### notes  
* at least 30m listening each day  
    - shadow  

#### reference
* [American Intonation - 1](https://raymondworkshop.github.io/language/american-intonation-1-2017-04-06/)  
* [Intonation 2](https://raymondworkshop.github.io/language/intonation-2-2020-01-14/)
* [英语口音纠正课程](https://open.163.com/newview/movie/free?pid=MDR81HCB8&mid=MDR81U0RL)
* [The Sounds of English: Elementary Course](https://mscharlotteacademy.teachable.com/courses/2078007/lectures/46784438)


#### dev-notes

-   Lean MVP

    -   time box your spec
        -   TODO
    -   write the spec
    -   cut your spec
    -   Don't fall in love with your MVP

-   tech

    -   use flask to implement a JSON API

        -   make flask render JSON, instead of having Flask render HTML

    -   frontend client consumes this API

    -   serve the static client from nginx proxy, and route api requests to uwsgi/gunicorn

-   learn more about NEXTJS

    -   TODO

-   setup the proj structure - flask + ~~nextjs~~ reactJS

    -   flask

        -   Flask backend is strictly an API server, we will never be serving complete pages

        > source l2env/bin/activate
        > python3 app.py

    -   reactJS lib

        -   Django Rest Framework and react using axios to make api calls
            REST is the most mainstream and easiest to find info on
            I deploy the react inside django(transfer build files into django) but can be deployed seperately as well.

    -   deploy on cloudflare

    -   block-party

        -   Our browser extension product, Privacy Party, is built in React.js and SCSS, with core automations primarily in JavaScript. The application backend is handled by a Python Flask service with a GraphQL API and persistent data backed by a Postgres database via SQLAlchemy/Alembic. Our cloud infrastructure is hosted on Render and AWS.

    -   dash or taipy

    -   LLM Applications with LangChain Tutorial
        -   llama-cpp-python

#### business ideas

-   the issues you are trying to solving

    -   time box your spec

-   mental health care

    -   AI therapy

        -   [认知行为治疗](https://www.jcthplus.org/article/what-is-cognitive-behavioral-therapy)

            -   情绪本身无好坏， 但是不舒服的情绪持续太久，太强烈， 便可能成为我们的重担；
                CBT 帮助我们观察和分析自己的想法，改善惯性， 打破恶性循环。

                -   我们的想法影响我们的情绪和行为

            -   we act based on how we think

                -   改善自己的想法，以改善情绪，行为和生活模式， 从而帮助管理压力，改善生活质素

            -   临床心理学家提供

                -   改善情绪困扰，包括社交焦虑症， 惊恐症，抑郁和焦虑症状
                -   以想法作切入点： 哪些想法是否符合客观事实， 检视或挑战固有想法和假设， 以协助你改变无益的想法和行为
                -   以行为为切入点： 了解行为反应的影响和后果， 选择其他合适的回应方法，或学习解难的技巧

                -   认知行为治疗比较着重个人的改变能力， 对环境等外在因素着墨较少

        -   the teachings and methods of cognitive behavioral therapy (CBT)

            -   CBT is a talking therapy that can help you manage your problems by changing the way you think and behave.
                It's most commonly used to treat anxiety and depression

        -   alongside human therapy

    -   [Sonia](https://www.soniahealth.com/)

    -   [jcthplus](https://www.jcthplus.org/about-us)

    -   koko
    -   Tala thrive
        -   book a video or voice call with one of our therapists or coaches and to access support and resources to help you thrive, not just survive
        -   网上讲座
        -   小组治疗 或 工作坊 需要价格提供

-   anonymous peer support community

    -   competitors

        -   koko
        -   togetherall
        -   mindhk
        -   timelycare
        -   CanChat – Cantonese Empathetic Chatbot for Secondary School Student

    -   tech

-   AI related

    -   [langCSS](https://langcss.com/)

    -   speech studio 发音评估

-   2books

    -   free old books

-   turn data into insights, superfast and at scale

    -   zerosheets.com

        -   API using google sheet

    -   sundial
        -   turn data into insights, superfast and at scale

-   rootd

-   过期知名域名

    -   使用 AI 向这些网站提供内容

-   其实你有了 idea, 可以立马做个原型，自己同时做为开发者和用户，找找感觉。无论多粗糙都没关系，关键是能用起来。这样几次下来，就有感觉了，知道怎么把一个东西做成了。市场是否接受，是在这基础之上。你要是一开始不知道怎么启动第一个，可以把你的点子告诉我，我带你做一下。以后就可以自己开拓了。

#### reference

-   [Python+React](http://allynh.com/blog/adding-a-react-frontend-to-your-flask-project/)
-   [python+JS](https://vercel.com/guides/how-to-use-python-and-javascript-in-the-same-application)

-   [CS142: Web Applications (Spring 2023)](https://web.stanford.edu/class/cs142/lectures.html)
-   [react-tutorial](https://www.runoob.com/react/react-tutorial.html)
-   [react](https://react.dev/learn)
