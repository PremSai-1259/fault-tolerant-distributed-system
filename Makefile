.PHONY: test build load deploy status port-forward clean
test:
	pytest -q
build:
	for s in result marks attendance eligibility failure-detector; do docker build -t ft/$$s:local .; done
load:
	for s in result marks attendance eligibility failure-detector; do minikube image load ft/$$s:local; done
deploy:
	kubectl apply -f k8s/namespace.yaml && kubectl apply -f k8s/applications && kubectl apply -f k8s/monitoring && kubectl apply -f k8s/logging
status:
	kubectl -n fault-tolerance get deploy,pods,svc
port-forward:
	kubectl -n fault-tolerance port-forward svc/result-service 8000:8000
clean:
	kubectl delete namespace fault-tolerance --ignore-not-found
