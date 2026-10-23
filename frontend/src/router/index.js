import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/interview",
      name: "Interview",
      component: () => import("../views/Interview.vue"),
    },
    {
      path: "/report",
      name: "Report",
      component: () => import("../views/Report.vue"),
    },
    {
      path: "/login",
      name: "Login",
      component: () => import("../views/Login.vue"),
    },
    {
      path: "/home",
      name: "Home",
      component: () => import("../views/Home.vue"),
    },
  ],
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("token");
  if (to.name !== "Login" && !token) next({ name: "Login" });
  else next();
});
export default router;
